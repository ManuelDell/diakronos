<template>
  <div class="dk-screen dk-screen-enter">
    <!-- OP-UI-19: Laden, Fehler und „nicht gefunden“ sind drei eigene Zustände. -->
    <DkSkelett v-if="ladenSkelett" form="zeilen" :anzahl="6" text="Beitrag wird geladen …" />

    <div v-else-if="fehler" class="bt-detail-fehler">
      <p class="bt-detail-fehlertext">{{ fehler }}</p>
      <div class="bt-detail-fehlerknoepfe">
        <DkButton variant="secondary" size="md" @click="zurueck($event)">
          <span class="bt-pfeil" aria-hidden="true">‹</span> Zurück zu den Beiträgen
        </DkButton>
        <!-- „Erneut versuchen“ nur, wenn ein neuer Versuch etwas ändern kann
             (Verbindung, Server). Bei „nicht gefunden“ und „keine Berechtigung“
             bliebe der Knopf ohne Wirkung — der nächste Schritt steht im Satz. -->
        <DkButton v-if="erneutSinnvoll" variant="secondary" size="md" @click="ladenDaten">Erneut versuchen</DkButton>
      </div>
    </div>

    <template v-else-if="beitrag">
      <!-- Kopf: Titel + „‹ zurück“ (MT-7: eigene Unterseite statt Fenster) -->
      <DkPageHeader ref="kopf" :title="beitrag.title || 'Beitrag'" :krumen="krumen" :badges="kopfBadges">
        <template #actions>
          <DkButton class="bt-zurueck" variant="secondary" size="md" as="a" :href="zurueckZiel" @click="zurueck">
            <span class="bt-pfeil" aria-hidden="true">‹</span> zurück
          </DkButton>
        </template>
      </DkPageHeader>

      <!-- UI-R6d: Die R6-Knöpfe des früheren Detail-Fensters stehen jetzt
           HIER auf der Leseseite. Sichtbar nur, wenn der Server für diesen
           Beitrag `darf_bearbeiten` gemeldet hat (`darfBearbeiten`) — Regel in
           `composables/r6Detail.js`, der Server entscheidet.
           UI-R6e: Das alte „⋯"-Menü ist entfallen; Bearbeiten/Löschen stehen
           NUR hier, an EINEM Recht (`darf_bearbeiten` des Details). -->
      <div v-if="darfAendern" class="bt-detail-knoepfe">
        <DkButton variant="secondary" size="md" @click="gastFreigeben()">Für Gäste freigeben</DkButton>
        <DkButton variant="secondary" size="md" @click="bearbeiten()">Bearbeiten</DkButton>
        <DkButton variant="danger" size="md" @click="loeschen()">Löschen</DkButton>
      </div>

      <article class="bt-lese">
        <div v-if="beitrag.image" class="bt-lese-bild">
          <img :src="beitrag.image" :alt="beitrag.title || ''" />
        </div>
        <div v-else class="bt-lese-bild bt-lese-bild--platz" :class="`cat-${beitrag.category}`" aria-hidden="true" />

        <div class="bt-lese-meta">
          <div class="bt-lese-person">
            <div class="dk-avatar dk-avatar-sm" aria-hidden="true">{{ autorKuerzel }}</div>
            <span>{{ beitrag.author }}</span>
          </div>
          <span>{{ formatDate(beitrag.date) }}</span>
        </div>

        <div class="dk-lesetext bt-lese-inhalt" v-html="sanitize(beitrag.content)" />

        <!-- Kommentare -->
        <section class="bt-lese-kommentare" aria-labelledby="bt-kommentare-titel">
          <h2 id="bt-kommentare-titel" class="bt-lese-zwischentitel">
            Kommentare ({{ beitrag.comments || 0 }})
          </h2>
          <p v-if="!kommentare.length" class="bt-lese-leer">
            Noch kein Kommentar. Schreib den ersten.
          </p>
          <div v-for="c in kommentare" :key="c.id" class="bt-kommentar">
            <div class="dk-avatar dk-avatar-md" aria-hidden="true">{{ c.avatar }}</div>
            <div class="bt-kommentar-text">
              <div class="bt-kommentar-kopf">
                <strong>{{ c.author }}</strong>
                <span>{{ formatDate(c.date) }}</span>
              </div>
              <p>{{ c.text }}</p>
            </div>
          </div>

          <form class="bt-kommentar-form" @submit.prevent="addComment">
            <input
              v-model="newComment"
              type="text"
              class="dk-ui-eingabe"
              aria-label="Kommentar schreiben"
              placeholder="Kommentar schreiben…"
            />
            <DkButton variant="primary" size="md" type="submit" :disabled="addingComment" :loading="addingComment">
              Absenden
            </DkButton>
          </form>
        </section>
      </article>
    </template>

    <!-- UI-R6d: Gast-Link für DIESEN Beitrag. Der Dialog öffnet nur über
         „Für Gäste freigeben“, und der erscheint nur mit `darf_bearbeiten`. -->
    <GastFreigabe
      :model-value="gastOffen"
      typ="beitrag"
      :objekt="beitrag?.id || ''"
      :titel="beitrag?.title || ''"
      @update:model-value="gastOffen = $event"
    />
  </div>
</template>

<script setup>
/**
 * BeitragDetail — EIN Beitrag als eigene Unterseite (MT-7).
 *
 * Befund: „Beitrag lesen“ öffnete ein Fenster (DkDialog) — keine eigene
 * Adresse, Zurück-Knopf des Browsers führte nicht zum Artikel zurück, kein
 * Drucken. Das SOLL ist eine Unterseite mit eigener Adresse,
 * Kopf mit Titel und „‹ zurück“, Lesebreite und druckbarer Ansicht.
 *
 * Adresse: `#/beitraege/<Kennung>` (Router: BeitragDetail). Die Liste
 * (`Beitraege.vue`) bleibt unverändert in ihrer Aufgabe und verlinkt je Karte
 * auf diese Adresse. Rechte sind unverändert — es ist nur Darstellung:
 * Lesen darf jeder Angemeldete (`get_beitrag_detail`), der Server prüft
 * weiterhin.
 *
 * UI-R6d: „Für Gäste freigeben“, „Bearbeiten“ und „Löschen“ sind von den
 * Detail-FENSTERN der Listen hierher gezogen. Sie hängen AUSSCHLIESSLICH an
 * `darf_bearbeiten` aus der Serverantwort (`darfBearbeiten` in
 * `composables/r6Detail.js`) — nicht an `isAdmin`.
 *
 * UI-R6e: `get_beitrag_detail` liefert `darf_bearbeiten` selbst (R-12l) — das
 * Recht kommt DIREKT aus der Detail-Antwort, die Seite holt dafür keine Liste
 * mehr (`detailMitListe` ist hier entfallen). Das alte „⋯“-Menü (`DkAktionen`,
 * an `isAdmin`) ist gestrichen: Bearbeiten/Löschen hatten damit zwei Quellen
 * (ein Admin ohne Recht sah sie, ein Admin mit Recht doppelt). Die Knöpfe sind
 * jetzt die EINE Stelle.
 *
 * Farben/Abstände ausschließlich aus tokens.css; Icons stehen auf der
 * Textlinie (Flex `align-items: center`), keine eigenen Farbwerte.
 */
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import DOMPurify from 'dompurify'
import { apiCall } from '../composables/useApi.js'
import { useLadeSkelett } from '../composables/useLadeSkelett.js'
import { aktionsfehler, fehlertext, zustandFuer } from '../../shared/fehlertexte.js'
import { showToast } from '../composables/useToast.js'
import { papierkorbMeldung, wiederherstellen } from '../composables/papierkorb.mjs'
import { useRueckgaengigAktion } from '../composables/useRueckgaengigAktion.js'
import { getRouteParam, navigate } from '../router.js'
// MT-7b (Operator-Entscheidung): „‹ zurück“ springt auf die gemerkte
// Listen-Adresse MIT Filtern — kein `history.back()` mehr (die Leseseite las
// ihren eigenen Verlaufs-Eintrag, das Merkmal der Liste galt dort nie) und
// kein Push (der Zurück-Knopf des Browsers führte sonst im Kreis).
import { rueckwegErsetzen, rueckwegZiel } from '../composables/zurueckWege.mjs'
// UI-R6d/R6e: Das Recht kommt aus `darf_bearbeiten` der DETAIL-Antwort
// (Server, R-12l) — EINE Regel für Beiträge und Wiki (`r6Detail.js`).
import { darfBearbeiten } from '../composables/r6Detail.js'
import GastFreigabe from '../components/r6/GastFreigabe.vue'
import DkPageHeader from '../components/ui/DkPageHeader.vue'
import DkButton from '../components/ui/DkButton.vue'
import DkSkelett from '../components/ui/DkSkelett.vue'

function sanitize(html) { return DOMPurify.sanitize(html || '') }

const KATEGORIEN = {
  ankuendigung: 'Ankündigung',
  gottesdienst: 'Gottesdienst',
  jugend: 'Jugend',
  gemeindeleben: 'Gemeindeleben',
  allgemein: 'Allgemein',
}
function categoryName(id) { return KATEGORIEN[id] || id || '' }

const { mitRueckgaengig } = useRueckgaengigAktion()

/** Darf der Server für diesen Beitrag ändern? (`darf_bearbeiten`, sonst nein.) */
const darfAendern = computed(() => darfBearbeiten(beitrag.value))

/* Gast-Link-Dialog (nur für Beiträge mit `darf_bearbeiten`). */
const gastOffen = ref(false)
function gastFreigeben() {
  if (!darfAendern.value) return
  gastOffen.value = true
}

/**
 * Die Kennung kommt aus der Adresse. `getRouteParam` liefert sie NUR, wenn die
 * Route diese Seite ist — beim bloßen Durchlaufen von `#/beitraege` (ein
 * Routenwechsel mit dieser Seite als Ziel) steht im Parameter-Objekt nichts.
 * Deshalb der Rückfall auf den Pfadteil der Adresse (wie MitgliedDetail).
 */
const beitragId = computed(() => {
  const ausRoute = getRouteParam('id', 'BeitragDetail')
  if (ausRoute) return ausRoute
  const treffer = /^#\/beitraege\/([^?#]+)/.exec(String(window.location.hash || ''))
  return treffer ? decodeURIComponent(treffer[1]) : ''
})
const beitrag = ref(null)
const fehler = ref('')
/** Zustand des Fehlers (Katalogschlüssel) — entscheidet über „Erneut versuchen“. */
const fehlerZustand = ref('')
const erneutSinnvoll = computed(() => !['weg', 'rechte'].includes(fehlerZustand.value))
const kopf = ref(null)
const laden = ref(true)
const { skelettSichtbar: ladenSkelett } = useLadeSkelett(laden)
const newComment = ref('')
const addingComment = ref(false)

/**
 * Der Weg zurück führt in die Liste — als echter Link (Mittelklick, Lesezeichen).
 * MT-7b: Das Ziel wird zur Laufzeit bestimmt (gemerkte Adresse mit Filtern,
 * sonst die Liste ohne Filter), damit der Link auch dann stimmt.
 */
const zurueckZiel = computed(() => rueckwegZiel('#/beitraege'))
const krumen = computed(() => [
  { text: 'Beiträge', href: zurueckZiel.value },
  { text: beitrag.value?.title || 'Beitrag' },
])
const kopfBadges = computed(() => (
  beitrag.value?.category ? [{ text: categoryName(beitrag.value.category), variant: 'akzent' }] : []
))
const autorKuerzel = computed(() => {
  const teile = String(beitrag.value?.author || '').trim().split(/\s+/).filter(Boolean)
  return (teile.slice(0, 2).map((t) => t[0]).join('') || '?').toUpperCase()
})
const kommentare = computed(() => beitrag.value?.commentList || [])

/**
 * Zurück (MT-7b): KEIN `history.back()`, KEIN Push. Der Knopf ERSETZT den
 * eigenen Verlaufs-Eintrag durch die Listen-Adresse aus dem Merker (mit
 * Filtern; ohne Merker die Liste ohne Filter). Vorher lief `navigate(ziel)`
 * — das setzt `location.hash` und legt einen neuen Eintrag an, sodass der
 * Zurück-Knopf des Browsers wieder auf der Leseseite landete (Zurück-Falle).
 */
function zurueck(ereignis) {
  // Modifier erst prüfen, dann abschalten: Strg-/Umschalt-/Mittelklick soll den
  // Link normal in einem neuen Tab öffnen (wie bei „Ähnliche Artikel“).
  if (ereignis && (ereignis.button > 0 || ereignis.metaKey || ereignis.ctrlKey || ereignis.shiftKey || ereignis.altKey)) return
  ereignis?.preventDefault?.()
  rueckwegErsetzen('#/beitraege')
}

async function ladenDaten() {
  const id = beitragId.value
  if (!id) {
    fehlerZustand.value = 'weg'
    fehler.value = fehlertext(null, { zustand: 'weg' })
    laden.value = false
    return
  }
  laden.value = true
  fehler.value = ''
  try {
    const detail = await apiCall('beitraege.get_beitrag_detail', { beitrag_id: id })
    if (!detail) {
      fehlerZustand.value = 'weg'
      fehler.value = fehlertext(null, { zustand: 'weg' })
      beitrag.value = null
      return
    }
    // UI-R6e: `darf_bearbeiten` kommt aus dem DETAIL selbst (R-12l) — die
    // Leseseite braucht dafür keine Liste mehr. Der Server entscheidet.
    beitrag.value = {
      ...detail,
      commentList: detail.commentList || [],
    }
  } catch (err) {
    // UX2g (Review-Punkt 4): Der Server unterscheidet die Lagen — gelöscht/
    // unveröffentlicht/unbekannt gibt DoesNotExistError (404), fehlendes Recht
    // 403. Vorher stand hier für JEDEN Fall „Prüfe die Verbindung …“; jetzt
    // sagt der Katalog was los ist, und „Erneut versuchen“ erscheint nur, wo
    // es etwas bringen kann.
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
  if (beitrag.value) fokusAufTitel()
}

async function addComment() {
  if (addingComment.value) return
  if (!newComment.value.trim() || !beitrag.value) return
  addingComment.value = true
  try {
    const res = await apiCall('beitraege.create_kommentar', {
      beitrag_id: beitrag.value.id,
      text: newComment.value.trim(),
    })
    if (res?.success && res.kommentar) {
      beitrag.value.commentList = [...kommentare.value, res.kommentar]
      beitrag.value.comments = (beitrag.value.comments || 0) + 1
      newComment.value = ''
    }
  } catch (err) {
    showToast(aktionsfehler('speichern', err), 'error')
  } finally {
    addingComment.value = false
  }
}

/* ── Änderungs-Knöpfe (UI-R6d/R6e) — EINE Stelle, EIN Recht ───────────────
   `darfAendern` (`darf_bearbeiten`) steht direkt am Beitrag; `bearbeiten`
   und `loeschen` werden NUR von den Knöpfen oben gerufen. Das frühere
   „⋯“-Menü (`DkAktionen`, an `isAdmin`) ist gestrichen: ein Admin ohne Recht
   sah die Einträge, ein Admin mit Recht sah sie doppelt. */
async function bearbeiten() {
  navigate(`#/beitraege?bearbeiten=${encodeURIComponent(beitrag.value.id)}`)
}
async function loeschen() {
  const ziel = beitrag.value
  if (!ziel) return
  // MT-7b: Auch nach dem Löschen zurück auf die gemerkte Listen-Adresse —
  // VOR dem Sprung lesen, denn der Merker gehört der Liste.
  const rueckweg = zurueckZiel.value
  try {
    const antwort = await apiCall('beitraege.delete_beitrag', { beitrag_id: ziel.id })
    navigate(rueckweg)
    await mitRueckgaengig({
      beschreibung: papierkorbMeldung(ziel.title, antwort?.wiederherstellbar_bis),
      zurueck: () => wiederherstellen('beitrag', ziel.id),
      erfolg: `„${ziel.title}“ wiederhergestellt.`,
    })
  } catch (err) {
    showToast(aktionsfehler('löschen', err), 'error')
  }
}

/* ── Anzeige ─────────────────────────────────────────────────────────────── */
function formatDate(d) {
  if (!d) return ''
  return new Date(d).toLocaleDateString('de-DE', { day: '2-digit', month: 'short', year: 'numeric' })
}

/**
 * Fokus auf die Überschrift der Seite (Review-Punkt 7): nach dem Aufbau einer
 * Detailseite stünde der Fokus sonst auf `body` — Tastatur und Vorlesehilfe
 * beginnen wieder oben im Gerüst statt beim Inhalt. `tabindex="-1"` macht die
 * h1 programmatisch erreichbar, ohne sie in den Tab-Strom zu nehmen.
 */
function fokusAufTitel() {
  const el = kopf.value?.$el?.querySelector?.('.dk-ui-pageheader-titel')
  if (!el) return
  el.setAttribute('tabindex', '-1')
  el.focus({ preventScroll: true })
}

async function seiteAufbauen() {
  await ladenDaten()
}

onMounted(seiteAufbauen)
// Wechselt die Kennung in der Adresse (Link auf einen anderen Beitrag), wird
// derselbe Inhalt neu geladen — die Seite bleibt stehen, nur der Beitrag wechselt.
watch(beitragId, () => { if (beitragId.value) seiteAufbauen() })
</script>

<style scoped>
/* ── Leseansicht ─────────────────────────────────────────────────────────────
   Eine Fläche, Lesebreite (--lesebreite), keine Rahmen (Ä2). */
.bt-lese {
  background: var(--surface);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow);
  padding: var(--pad);
}

.bt-lese-bild {
  border-radius: var(--radius);
  overflow: hidden;
  margin-bottom: var(--sp-4);
}
.bt-lese-bild img { display: block; width: 100%; height: auto; max-height: 360px; object-fit: cover; }
.bt-lese-bild--platz { height: 160px; background: var(--surface-2); }
.bt-lese-bild--platz.cat-ankuendigung  { background: color-mix(in oklch, var(--dk-cat-ankuendigung) 16%, var(--surface-2)); }
.bt-lese-bild--platz.cat-gottesdienst  { background: color-mix(in oklch, var(--dk-cat-gottesdienst) 16%, var(--surface-2)); }
.bt-lese-bild--platz.cat-jugend        { background: color-mix(in oklch, var(--dk-cat-jugend) 16%, var(--surface-2)); }
.bt-lese-bild--platz.cat-gemeindeleben { background: color-mix(in oklch, var(--dk-cat-gemeindeleben) 16%, var(--surface-2)); }
.bt-lese-bild--platz.cat-allgemein     { background: color-mix(in oklch, var(--dk-cat-allgemein) 16%, var(--surface-2)); }

/* Kopfdaten: Person, Datum — Symbol und Text auf einer Linie (Auflage 04.11.). */
.bt-lese-meta {
  display: flex;
  align-items: center;
  gap: var(--sp-4);
  flex-wrap: wrap;
  font-size: var(--fs-sm);
  color: var(--muted);
  margin-bottom: var(--sp-4);
}
.bt-lese-person { display: flex; align-items: center; gap: var(--sp-2); }

.bt-lese-inhalt { font-size: var(--fs); line-height: 1.7; color: var(--text); }
.bt-lese-inhalt :deep(p) { margin: 0 0 var(--sp-3); }
.bt-lese-inhalt :deep(ul),
.bt-lese-inhalt :deep(ol) { margin: 0 0 var(--sp-3); padding-left: var(--sp-5); }
.bt-lese-inhalt :deep(li) { margin-bottom: var(--sp-1); }
.bt-lese-inhalt :deep(h2),
.bt-lese-inhalt :deep(h3) { font-size: var(--fs-h3); font-weight: var(--fw-h); color: var(--text); margin: var(--sp-5) 0 var(--sp-2); }
.bt-lese-inhalt :deep(a) { color: var(--primary); }
.bt-lese-inhalt :deep(img) { max-width: 100%; height: auto; }
.bt-lese-inhalt :deep(table) { width: 100%; border-collapse: collapse; }
.bt-lese-inhalt :deep(td) { padding: var(--sp-2); }
.bt-lese-inhalt :deep(strong) { color: var(--text); }

/* Kommentare */
.bt-lese-kommentare { margin-top: var(--sp-6); }
.bt-lese-zwischentitel { font-size: var(--fs-h4); font-weight: var(--fw-h); color: var(--text); margin: 0 0 var(--sp-3); }
.bt-lese-leer { font-size: var(--fs-sm); color: var(--muted); margin: 0 0 var(--sp-3); }
.bt-kommentar { display: flex; gap: var(--sp-3); padding: var(--sp-3) 0; align-items: flex-start; }
/* Ä2/S3: Abstand statt Trennlinie — die Kommentare trennen sich über Weißraum. */
.bt-kommentar-text { flex: 1; min-width: 0; }
.bt-kommentar-kopf { display: flex; align-items: center; gap: var(--sp-2); margin-bottom: var(--sp-1); }
.bt-kommentar-kopf strong { font-size: var(--fs-sm); color: var(--text); }
.bt-kommentar-kopf span { font-size: var(--fs-xs); color: var(--muted); }
.bt-kommentar-text p { font-size: var(--fs-sm); color: var(--muted); margin: 0; }

.bt-kommentar-form { display: flex; gap: var(--sp-2); margin-top: var(--sp-4); align-items: center; }
.bt-kommentar-form input { flex: 1; min-width: 0; }

/* UI-R6d: die drei Änderungs-Knöpfe (Freigeben/Bearbeiten/Löschen) — eigene
   Zeile unter dem Kopf, rechtsbündig. Seit UI-R6e die EINZIGE Stelle für
   Bearbeiten/Löschen (das „⋯“-Menü der Seite ist entfallen). */
.bt-detail-knoepfe { display: flex; align-items: center; justify-content: flex-end; gap: var(--sp-2); flex-wrap: wrap; margin-bottom: var(--sp-4); }
.bt-pfeil { display: inline-flex; align-items: center; line-height: 1; font-size: var(--fs-h4); margin-right: var(--sp-1); }

/* Fehlerzustand */
.bt-detail-fehler { display: flex; flex-direction: column; gap: var(--sp-4); padding: var(--pad); }
.bt-detail-fehlertext { margin: 0; font-size: var(--fs); color: var(--text); }
.bt-detail-fehlerknoepfe { display: flex; gap: var(--sp-3); flex-wrap: wrap; }

/* Am Handy: Kopf-Aktionen unter dem Titel, Formular untereinander (K4: 44 px). */
@media (max-width: 700px) {
  .bt-kommentar-form { flex-direction: column; align-items: stretch; }
  .bt-detail-knoepfe { justify-content: flex-start; }
}

/* Druck: nur der Beitrag, ohne Gerüst — schwarz auf weiß, volle Breite. */
@media print {
  /* MT-7c: „‹ zurück“ sitzt im `#actions`-Slot des Seitenkopfs und wurde
     mitgedruckt (ausgeblendet war nur die Aktions-Leiste der Seite). */
  .bt-zurueck { display: none; }
  /* UI-R6d: Die Änderungs-Knöpfe sind Arbeit am Beitrag, nicht Inhalt —
     im Druck haben sie nichts zu suchen (wie „‹ zurück“, MT-7c). */
  .bt-detail-knoepfe { display: none; }
  .bt-lese { box-shadow: none; padding: 0; background: transparent; }
  .bt-lese-inhalt { max-width: none; }
  .bt-kommentar-form { display: none; }
}
</style>
