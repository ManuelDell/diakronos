<template>
  <div class="dk-screen dk-screen-enter">
    <!-- UX3a (Konzept-Entscheidung): Das Werkzeug heißt „Website-Baukasten“,
         nicht „Primo“ — „Primo“ ist nur der technische Anbieter (WEB-1). -->
    <DkPageHeader title="Website" sub="Was von der Gemeinde auf der Website erscheint — bearbeitet im Website-Baukasten." />

    <div v-if="!darfVerwalten" class="wf-bereich">
      <DkHint variant="warn" role="alert">
        Die Website-Freigaben sind für Systemmanager, Administratoren und
        Website-Moderatoren. Dein Konto hat keine dieser Rollen.
      </DkHint>
    </div>

    <div v-else class="wf-bereich">
      <!-- Abschnitte haben eigene Kennungen (data-wf-abschnitt), damit sie
           ohne Tooltip-Rollen-Auswertung ansprechbar sind: `has_text`
           beruecksichtigt auch `title`-Attribute, und die Kuerzel-Felder
           tragen den Namen ihres Abschnitts („Kuerzel fuer Gruppe 3“). -->
      <!-- ── U5 · Kurzanleitung, Zustand und Weg nach Primo ─────────────── -->
      <div data-wf-abschnitt="kopf">
      <DkCard title="Website-Freigaben">
        <div class="wf-kopf">
          <ol class="wf-anleitung">
            <li v-for="(satz, i) in anleitung" :key="i">{{ satz }}</li>
          </ol>

          <div class="wf-zustand">
            <DkBadge :variant="zustand().ton">{{ zustand().titel }}</DkBadge>
            <span v-if="details()" class="wf-details">{{ details() }}</span>
          </div>
          <p class="wf-hilfe">{{ zustand().text }}</p>
          <p class="wf-hilfe">{{ SITZUNGS_HINWEIS }}</p>

          <DkHint v-if="hinweis" :variant="hinweis.ton" role="alert">{{ hinweis.text }}</DkHint>

          <div class="wf-aktionen">
            <DkButton variant="primary" :loading="oeffnet" :disabled="!verbunden"
              @click="primoOeffnen">
              Website-Baukasten öffnen
            </DkButton>
            <DkButton variant="secondary" :loading="laedt" @click="laden">
              Stand neu laden
            </DkButton>
          </div>

          <p v-if="!verbunden" class="wf-hilfe">
            Die Einrichtung der Anbindung steht in den Einstellungen unter
            „Website-Baukasten“. Die Freigaben hier lassen sich auch ohne
            Anbindung pflegen — sie wirken, sobald die Website verbunden ist.
          </p>
        </div>
      </DkCard>
      </div>

      <DkHint v-if="fehler" variant="err" role="alert">{{ fehler }}</DkHint>

      <!-- UX2d2: Platzhalter erst nach 300 ms — schnelle Antworten flackern nicht. -->
      <DkSkelett v-if="freigabenSkelett" form="zeilen" :anzahl="3" text="Freigaben werden geladen …" />

      <template v-else-if="daten">
        <!-- ── U1 · Kalender ───────────────────────────────────────────── -->
        <div data-wf-abschnitt="kalender">
        <DkCard title="Kalender">
          <p class="wf-hilfe">
            Ein freigegebener Kalender zeigt seine Termine auf der Website.
            Titel, Zeit, Ort und Beschreibung der Termine werden dabei
            öffentlich — auch interne Notizen in der Beschreibung.
          </p>
          <DkCheckbox v-model="nurFreigegebene">
            Nur freigegebene Kalender zeigen
          </DkCheckbox>

          <DkEmpty v-if="!kalender.length" title="Keine Kalender"
            text="Sobald Kalender angelegt sind, erscheinen sie hier." />
          <div v-else class="wf-liste">
            <FreigabeZeile
              v-for="k in sichtbareKalender"
              :key="k.name"
              :titel="k.titel"
              :name="k.name"
              :freigabe="k.freigabe"
              :slug="k.slug"
              :nur-oeffentliche-kategorien="k.nurOeffentlicheKategorien"
              :zeige-kategorie-schalter="true"
              :kategori-hinweis="kategorieHinweis(oeffentlicheKategorien)"
              :laeuft="laeuft(`kalender:${k.name}`)"
              :fehler="zeilenFehler(`kalender:${k.name}`)"
              @freigabe="kalenderFreigabe(k, $event)"
              @nur-oeffentliche-kategorien="kalenderKategorien(k, $event)"
              @slug="kalenderSlug(k, $event)"
            />
          </div>
          <p class="wf-hilfe">
            „Nur öffentliche Terminarten“ lässt nur Termine durch, deren
            Terminart unten als öffentlich freigegeben ist.
          </p>
        </DkCard>
        </div>

        <!-- ── U1b · Terminarten (steuert die Einschränkung oben) ──────── -->
        <div data-wf-abschnitt="terminarten">
        <DkCard title="Terminarten">
          <p class="wf-hilfe">
            Welche Art von Termin überhaupt öffentlich erscheinen darf. Die
            Einschränkung „Nur öffentliche Terminarten“ eines Kalenders greift
            auf diese Schalter zurück.
          </p>
          <DkHint :variant="oeffentlicheKategorien ? 'info' : 'warn'">
            {{ kategorieHinweis(oeffentlicheKategorien) }}
          </DkHint>
          <DkEmpty v-if="!kategorien.length" title="Keine Terminarten"
            text="Sobald Terminarten angelegt sind, erscheinen sie hier." />
          <ul v-else class="wf-kategorien">
            <li v-for="k in kategorien" :key="k.name" class="wf-kategorie">
              <DkCheckbox
                :model-value="k.oeffentlich"
                :disabled="laeuft(`kategorie:${k.name}`)"
                @update:model-value="kategorieUmschalten(k, $event)"
              >
                {{ k.titel }}
              </DkCheckbox>
            </li>
          </ul>
        </DkCard>
        </div>

        <!-- ── U2 · Gruppen ────────────────────────────────────────────── -->
        <div data-wf-abschnitt="gruppen">
        <DkCard title="Gruppen">
          <p class="wf-hilfe">
            Von einer freigegebenen Gruppe werden Name, Typ, Beschreibung,
            Treffzeit, Treffpunkt und Bild öffentlich. Personen (Mitglieder,
            Mitarbeiter, Leitung) erscheinen nicht.
          </p>
          <DkEmpty v-if="!gruppen.length" title="Keine Gruppen"
            text="Sobald Gruppen angelegt sind, erscheinen sie hier." />
          <div v-else class="wf-liste">
            <FreigabeZeile
              v-for="g in gruppen"
              :key="g.name"
              :titel="g.titel"
              :name="g.name"
              :freigabe="g.freigabe"
              :slug="g.slug"
              :laeuft="laeuft(`gruppe:${g.name}`)"
              :fehler="zeilenFehler(`gruppe:${g.name}`)"
              @freigabe="gruppeFreigabe(g, $event)"
              @slug="gruppeSlug(g, $event)"
            />
          </div>
        </DkCard>
        </div>

        <!-- ── U3 · Beiträge ───────────────────────────────────────────── -->
        <div data-wf-abschnitt="beitraege">
        <DkCard title="Beiträge">
          <p class="wf-anzahl">
            <strong>{{ beitraegeZahl }}</strong>
            {{ beitraegeZahl === 1 ? 'Beitrag steht' : 'Beiträge stehen' }} auf der Website.
          </p>
          <p class="wf-hilfe">
            Öffentlich ist ein Beitrag nur, wenn er zusätzlich veröffentlicht
            ist. Den Schalter „Auf Website“ findest du in der Beitragsliste
            unter „Beiträge“ — dort, wo Beiträge geschrieben und veröffentlicht
            werden.
          </p>
          <DkButton variant="secondary" @click="zuBeitraegen">Zu den Beiträgen</DkButton>
        </DkCard>
        </div>

        <!-- ── U4 · Kontakt-Postfächer ─────────────────────────────────── -->
        <div data-wf-abschnitt="postfaecher">
        <DkCard title="Kontakt-Postfächer">
          <template #actions>
            <DkButton size="md" variant="secondary" @click="postfachNeu">Postfach anlegen</DkButton>
          </template>
          <p class="wf-hilfe">
            Empfänger der Nachrichten aus dem Kontaktformular der Website.
            Ohne eigene Zeile gilt die in der Konfiguration hinterlegte
            Adresse.
          </p>
          <DkHint :variant="postfachStand.ton">{{ postfachStand.text }}</DkHint>

          <DkTable
            :spalten="postfachSpalten"
            :leer="!postfaecher.length"
            leer-titel="Keine eigenen Postfächer"
            leer-text="Es gilt die Adresse aus der Konfiguration."
          >
            <tr v-for="p in postfaecher" :key="p.slug">
              <td>{{ p.bezeichnung }}</td>
              <td><code class="wf-slug">/{{ p.slug }}</code></td>
              <td class="wf-mail">{{ p.email }}</td>
              <td>{{ p.aktiv === true ? 'aktiv' : 'aus' }}</td>
              <td class="is-aktion">
                <DkButton size="md" variant="ghost" @click="postfachBearbeiten(p)">Bearbeiten</DkButton>
                <DkButton size="md" variant="danger" :loading="laeuft(`postfach:${p.slug}`)"
                  @click="postfachEntfernen(p)">
                  Löschen
                </DkButton>
              </td>
            </tr>
          </DkTable>
        </DkCard>
        </div>
      </template>

      <DkHint v-else variant="info">
        Die Freigaben konnten nicht geladen werden. Bitte die Seite neu laden.
      </DkHint>
    </div>

    <!-- Postfach-Dialog (U4) -->
    <DkDialog
      :model-value="postfachDialog"
      :title="postfachFormular.istNeu ? 'Postfach anlegen' : 'Postfach bearbeiten'"
      size="sm"
      @update:model-value="postfachDialog = $event"
    >
      <form class="wf-formular" @submit.prevent="postfachSpeichern">
        <!-- UX2f: Feld mit Prüfung — die Meldung steht am Feld (beim Verlassen,
             danach beim Tippen); die Sammelprüfung beim Speichern bleibt. -->
        <DkField label="Bezeichnung" required :error="postfachFelder.bezeichnung"
          :regel="regelPostfachName" :wert="postfachFormular.bezeichnung"
          pflicht-name="eine Bezeichnung" :maxlength="BEZEICHNUNG_MAX"
          v-slot="feld"
          @update:wert="postfachFormular.bezeichnung = $event">
          <input v-bind="feld.feldProps" type="text" placeholder="z. B. Allgemein" />
        </DkField>
        <DkField label="Kürzel" required :error="postfachFelder.slug"
          :help="postfachFormular.istNeu
            ? 'Name in der Adresse: Kleinbuchstaben, Ziffern, Bindestrich.'
            : 'Der Kürzel lässt sich nach dem Anlegen nicht ändern.'"
          :disabled="!postfachFormular.istNeu">
          <input v-model="postfachFormular.slug" class="dk-ui-eingabe" type="text"
            :maxlength="SLUG_MAX" :disabled="!postfachFormular.istNeu"
            autocomplete="off" spellcheck="false" placeholder="z. B. allgemein" />
        </DkField>
        <DkField label="E-Mail-Adresse" required :error="postfachFelder.email"
          :regel="regelPostfachEmail" :wert="postfachFormular.email"
          v-slot="feld"
          :maxlength="EMAIL_MAX" @update:wert="postfachFormular.email = $event">
          <input v-bind="feld.feldProps" type="email" placeholder="postfach@example.org" />
        </DkField>
        <DkField label="Reihenfolge" :error="postfachFelder.sortierung"
          help="Kleinere Zahl steht weiter oben.">
          <input v-model="postfachFormular.sortierung" class="dk-ui-eingabe" type="number"
            inputmode="numeric" step="10" />
        </DkField>
        <DkCheckbox v-model="postfachFormular.aktiv">Postfach ist aktiv</DkCheckbox>
        <DkHint v-if="postfachMeldung" variant="err" role="alert">{{ postfachMeldung }}</DkHint>
      </form>
      <template #footer>
        <DkButton variant="secondary" @click="postfachDialog = false">Abbrechen</DkButton>
        <DkButton variant="primary" :loading="postfachLaeuft" @click="postfachSpeichern">Speichern</DkButton>
      </template>
    </DkDialog>
  </div>
</template>

<script setup>
/**
 * BS-1d — Seite „Website“ mit dem Bereich „Website-Freigaben“.
 *
 * WEB-3 bleibt enthalten: Zustand der Primo-Anbindung und „Primo öffnen“
 * (POST-Übergabe, Token nur im Fragment, nie im Zustand).
 *
 * Fünf Abschnitte (Karte BS-1d):
 *   U1 Kalender        Schalter „Auf Website zeigen“, Kürzel, „Nur öffentliche
 *                      Terminarten“, Warnung vor dem Einschalten (komplette
 *                      Beschreibung!) und die Terminarten-Schalter, auf die die
 *                      Einschränkung sich stützt.
 *   U2 Gruppen         Schalter + Kürzel, Hinweis auf die öffentlichen Felder.
 *   U3 Beiträge        Anzahl „auf Website“ + Weg in die vorhandene
 *                      Beitragsbearbeitung (der Schalter sitzt dort, nicht hier,
 *                      weil die Beiträge dieser App über die API-Endpunkte
 *                      `beitraege.*` laufen und nicht über `Beitrag`-Datensätze).
 *   U4 Postfächer      Tabelle anlegen/bearbeiten/löschen + Hinweis auf die
 *                      Adresse aus der Konfiguration.
 *   U5 Kurzanleitung   vier Sätze + „Primo öffnen“.
 *
 * Sichtbarkeit: nur System Manager, Administrator, Website-Moderator
 * (`darfFreigabenVerwalten`); der Server weist zusätzlich mit 403 ab.
 *
 * Schreibende Aufrufe gehen ausschließlich per `apiCall` (POST mit
 * CSRF-Token) über `useWebsiteFreigaben` — nie über ein GET. Die Vorwarnung
 * und die Slug-Prüfung stehen in `shared/website-freigaben.mjs` (prüfbar).
 */
import { computed, onMounted, ref } from 'vue'
import { useSession } from '../composables/useSession.js'
import { useWebsiteFreigaben } from '../composables/useWebsiteFreigaben.js'
import { useWebsite, oeffneInNeuemTab } from '../composables/useWebsite.js'
import { sitzungsHinweis } from '../composables/website.mjs'
import { showToast } from '../composables/useToast.js'
import { bestaetigen } from '../composables/useBestaetigen.js'
import {
  BEZEICHNUNG_MAX,
  EMAIL_MAX,
  SLUG_MAX,
  beitraegeAufWebsite,
  darfFreigabenVerwalten,
  freigabeNutzlast,
  gruppenWarnung,
  kalenderWarnung,
  kategorieHinweis,
  kurzanleitung,
  naechsteSortierung,
  postfachHinweis,
  postfachPruefen,
} from '../../shared/website-freigaben.mjs'
import DkBadge from '../components/ui/DkBadge.vue'
import DkButton from '../components/ui/DkButton.vue'
import DkCard from '../components/ui/DkCard.vue'
import DkCheckbox from '../components/ui/DkCheckbox.vue'
import DkDialog from '../components/ui/DkDialog.vue'
import DkEmpty from '../components/ui/DkEmpty.vue'
import DkField from '../components/ui/DkField.vue'
// UX2f: Prüfregeln aus EINER Quelle (Feld und Sammelprüfung).
import { pflicht, email as emailRegel, laenge as laengeRegel } from '../composables/feldPruefung.mjs'
import DkHint from '../components/ui/DkHint.vue'
import DkPageHeader from '../components/ui/DkPageHeader.vue'
import DkSkelett from '../components/ui/DkSkelett.vue'
import { useLadeSkelett } from '../composables/useLadeSkelett.js'
import DkTable from '../components/ui/DkTable.vue'
import FreigabeZeile from '../components/website/FreigabeZeile.vue'

// WEB-1b (D): Default 14400 s = 4 h. Die Oberfläche nennt die Dauer, weil sie
// sich nicht verlängert.
const SITZUNGS_HINWEIS = sitzungsHinweis(14400)

const { rollen } = useSession()
const darfVerwalten = computed(() => darfFreigabenVerwalten({ rollen: rollen.value }))

const {
  daten, laedt, fehler, laeuft, kalender, gruppen, postfaecher, kategorien,
  laden, freigabeSetzen, postfachSpeichern: postfachSchreiben,
  postfachLoeschen, kategorieSetzen,
} = useWebsiteFreigaben()

// UX2d2: der Platzhalter erscheint erst, wenn das Laden merklich dauert.
const freigabenSkelettGrund = computed(() => laedt.value && !daten.value)
const { skelettSichtbar: freigabenSkelett } = useLadeSkelett(freigabenSkelettGrund)

/** Primo-Anbindung — Zustand und „Primo öffnen“ (WEB-3, unverändert). */
const { daten: primoDaten, pruefen, zustand, details, primoOeffnen: holeUndOeffne } = useWebsite()
const oeffnet = ref(false)
const verbunden = computed(() => primoDaten.value?.status === 'verbunden')

const anleitung = kurzanleitung()
const hinweis = ref(null)

/** Fehlermeldungen je Zeile (Server-Ablehnung, z. B. „Kürzel vergeben“). */
const zeilenFehlerMap = ref({})
function zeilenFehler(schluessel) {
  return zeilenFehlerMap.value[schluessel] || ''
}
function setzeZeilenFehler(schluessel, text) {
  const neu = { ...zeilenFehlerMap.value }
  if (text) neu[schluessel] = text
  else delete neu[schluessel]
  zeilenFehlerMap.value = neu
}

/* ── Kalender (U1) ────────────────────────────────────────────────────── */
const nurFreigegebene = ref(false)
const sichtbareKalender = computed(() => (
  nurFreigegebene.value ? kalender.value.filter((k) => k.freigabe) : kalender.value
))
const oeffentlicheKategorien = computed(() => kategorien.value.filter((k) => k.oeffentlich).length)
const beitraegeZahl = computed(() => beitraegeAufWebsite(daten.value))
const postfachStand = computed(() => postfachHinweis(daten.value))

/**
 * Einschalten nur nach Bestätigung — bei Kalendern mit der deutlichen Warnung
 * (komplette Beschreibung, interne Notizen). Ausschalten braucht keine.
 */
async function kalenderFreigabe(zeile, { an, slug }) {
  const schluessel = `kalender:${zeile.name}`
  if (an) {
    const ok = await bestaetigen({
      titel: 'Kalender auf der Website zeigen?',
      text: kalenderWarnung(zeile.titel),
      aktion: 'Freigeben',
    })
    if (!ok) return
  }
  const nutzlast = freigabeNutzlast({
    art: 'kalender',
    name: zeile.name,
    freigabe: an,
    slug,
    gespeicherterSlug: zeile.slug,
  })
  const ergebnis = await freigabeSetzen(nutzlast)
  setzeZeilenFehler(schluessel, ergebnis.ok ? '' : ergebnis.fehler)
}

async function kalenderKategorien(zeile, an) {
  const ergebnis = await freigabeSetzen({
    art: 'kalender', name: zeile.name, freigabe: zeile.freigabe,
    nur_oeffentliche_kategorien: an,
  })
  if (!ergebnis.ok) setzeZeilenFehler(`kalender:${zeile.name}`, ergebnis.fehler)
}

async function kalenderSlug(zeile, slug) {
  const ergebnis = await freigabeSetzen({
    art: 'kalender', name: zeile.name, freigabe: zeile.freigabe, slug,
  })
  const schluessel = `kalender:${zeile.name}`
  setzeZeilenFehler(schluessel, ergebnis.ok ? '' : ergebnis.fehler)
  if (ergebnis.ok) showToast('Kürzel gespeichert')
}

/* ── Gruppen (U2) ─────────────────────────────────────────────────────── */
async function gruppeFreigabe(zeile, { an, slug }) {
  const schluessel = `gruppe:${zeile.name}`
  if (an) {
    const ok = await bestaetigen({
      titel: 'Gruppe auf der Website zeigen?',
      text: gruppenWarnung(zeile.titel),
      aktion: 'Freigeben',
    })
    if (!ok) return
  }
  const nutzlast = freigabeNutzlast({
    art: 'gruppe', name: zeile.name, freigabe: an, slug, gespeicherterSlug: zeile.slug,
  })
  const ergebnis = await freigabeSetzen(nutzlast)
  setzeZeilenFehler(schluessel, ergebnis.ok ? '' : ergebnis.fehler)
}

async function gruppeSlug(zeile, slug) {
  const ergebnis = await freigabeSetzen({
    art: 'gruppe', name: zeile.name, freigabe: zeile.freigabe, slug,
  })
  const schluessel = `gruppe:${zeile.name}`
  setzeZeilenFehler(schluessel, ergebnis.ok ? '' : ergebnis.fehler)
  if (ergebnis.ok) showToast('Kürzel gespeichert')
}

/* ── Terminarten (U1b) ────────────────────────────────────────────────── */
async function kategorieUmschalten(zeile, an) {
  const ergebnis = await kategorieSetzen(zeile.name, an)
  if (!ergebnis.ok) showToast(ergebnis.fehler, 'error')
}

/* ── Beiträge (U3) ────────────────────────────────────────────────────── */
function zuBeitraegen() {
  // Hash-Navigation der SPA — der Schalter „Auf Website“ sitzt im
  // Beitragseditor dieser Seite (`pages/Beitraege.vue`).
  window.location.hash = '#/beitraege'
}

/* ── Postfächer (U4) ──────────────────────────────────────────────────── */
const postfachDialog = ref(false)
const postfachMeldung = ref('')
const postfachLaeuft = ref(false)
// UX2f: Regeln der Postfach-Felder — dieselben Texte wie `postfachPruefen`
// (shared/website-freigaben.mjs), nur direkt am Feld angezeigt.
const regelPostfachName = (wert) =>
  pflicht('eine Bezeichnung')(wert) || laengeRegel({ max: BEZEICHNUNG_MAX, name: 'Die Bezeichnung' })(wert)
const regelPostfachEmail = (wert) =>
  pflicht('eine E-Mail-Adresse')(wert) || emailRegel()(wert)

const postfachFelder = ref({ slug: '', bezeichnung: '', email: '', sortierung: '' })
const postfachFormular = ref({
  slug: '', bezeichnung: '', email: '', aktiv: true, sortierung: '10', istNeu: true,
})

const postfachSpalten = [
  { key: 'bezeichnung', label: 'Bezeichnung' },
  { key: 'slug', label: 'Kürzel' },
  { key: 'email', label: 'E-Mail' },
  { key: 'aktiv', label: 'Zustand' },
  { key: 'aktion', label: 'Aktion', aktion: true },
]

function postfachNeu() {
  postfachFormular.value = {
    slug: '', bezeichnung: '', email: '', aktiv: true,
    sortierung: String(naechsteSortierung(postfaecher.value)), istNeu: true,
  }
  postfachFelder.value = { slug: '', bezeichnung: '', email: '', sortierung: '' }
  postfachMeldung.value = ''
  postfachDialog.value = true
}

function postfachBearbeiten(zeile) {
  postfachFormular.value = {
    slug: zeile.slug,
    bezeichnung: zeile.bezeichnung || '',
    email: zeile.email || '',
    aktiv: zeile.aktiv === true,
    sortierung: zeile.sortierung === undefined || zeile.sortierung === null
      ? ''
      : String(zeile.sortierung),
    istNeu: false,
  }
  postfachFelder.value = { slug: '', bezeichnung: '', email: '', sortierung: '' }
  postfachMeldung.value = ''
  postfachDialog.value = true
}

async function postfachSpeichern() {
  if (postfachLaeuft.value) return
  const formular = postfachFormular.value
  const pruefung = postfachPruefen({
    slug: formular.slug, bezeichnung: formular.bezeichnung, email: formular.email,
  })
  const sortierung = String(formular.sortierung ?? '').trim()
  const sortierungFehler = sortierung && !Number.isFinite(Number(sortierung))
    ? 'Die Reihenfolge muss eine Zahl sein.'
    : ''
  postfachFelder.value = { ...pruefung.felder, sortierung: sortierungFehler }
  postfachMeldung.value = ''
  if (!pruefung.ok || sortierungFehler) return

  const nutzlast = {
    slug: formular.slug.trim(),
    bezeichnung: formular.bezeichnung.trim(),
    email: formular.email.trim(),
    aktiv: formular.aktiv === true,
  }
  if (sortierung) nutzlast.sortierung = Number(sortierung)

  postfachLaeuft.value = true
  const ergebnis = await postfachSchreiben(nutzlast)
  postfachLaeuft.value = false
  if (!ergebnis.ok) {
    postfachMeldung.value = ergebnis.fehler
    return
  }
  postfachDialog.value = false
  showToast(formular.istNeu ? 'Postfach angelegt' : 'Postfach gespeichert')
}

async function postfachEntfernen(zeile) {
  const ok = await bestaetigen({
    titel: 'Postfach entfernen?',
    text: `„${zeile.bezeichnung || zeile.slug}“ wird entfernt. Nachrichten des `
      + 'Kontaktformulars gehen dann an ein anderes aktives Postfach — oder gar nicht mehr, '
      + 'wenn keines übrig ist.',
    aktion: 'Entfernen',
    gefahr: true,
  })
  if (!ok) return
  const ergebnis = await postfachLoeschen(zeile.slug)
  if (!ergebnis.ok) {
    showToast(ergebnis.fehler, 'error')
    return
  }
  showToast('Postfach entfernt')
}

/* ── Primo öffnen (WEB-3, unverändert) ───────────────────────────────── */
async function primoOeffnen() {
  oeffnet.value = true
  hinweis.value = null
  try {
    const ergebnis = await holeUndOeffne({ oeffne: oeffneInNeuemTab })
    if (!ergebnis.ok) {
      hinweis.value = { text: ergebnis.fehler, ton: 'err' }
      return
    }
    hinweis.value = {
      // Kein „Der Tab ist offen“ — das lässt sich mit `noopener` nicht
      // feststellen (window.open liefert dort immer null).
      text: 'Die Übergabe an den Website-Baukasten wurde gestartet. Der neue Tab sollte sich öffnen — '
        + 'ist er nicht zu sehen, bitte die Pop-up-Sperre für diese Seite prüfen '
        + 'und erneut versuchen.',
      ton: 'ok',
    }
  } finally {
    oeffnet.value = false
  }
}

onMounted(() => {
  if (!darfVerwalten.value) return
  laden()
  pruefen()
})
</script>

<style scoped>
.wf-bereich {
  /* FIX (Abnahme 2026-11-02, mobil 390 px): eine reine `gap`-Angabe erzeugt
     eine IMPLIZITE Spalte, die sich nach dem Inhalt richtet. Die Postfach-
     Tabelle (min-width 640px) zog den Bereich damit auf 678 px und die Texte
     liefen rechts aus dem Bild. `minmax(0, 1fr)` setzt die Spalte auf die
     Verfuegbare Breite; die Tabelle scrollt in ihrem eigenen `.dk-ui-table-wrap`. */
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: var(--sp-4);
  min-width: 0;
}
.wf-kopf { display: grid; grid-template-columns: minmax(0, 1fr); gap: var(--sp-3); min-width: 0; }
.wf-anleitung {
  margin: 0;
  padding-left: var(--sp-alt-20);
  display: grid;
  gap: var(--sp-1);
  color: var(--text);
}
.wf-aktionen { display: flex; flex-wrap: wrap; gap: var(--sp-3); }
.wf-zustand { display: flex; flex-wrap: wrap; align-items: center; gap: var(--sp-2); min-width: 0; }
.wf-details { color: var(--muted); font-size: var(--fs-sm); }
.wf-hilfe { margin: 0; display: block; color: var(--muted); font-size: var(--fs-sm); }
.wf-liste { display: grid; grid-template-columns: minmax(0, 1fr); min-width: 0; }
.wf-kategorien { display: grid; grid-template-columns: minmax(0, 1fr); gap: var(--sp-1); margin: 0; padding: 0; list-style: none; min-width: 0; }
.wf-kategorie { min-width: 0; }
.wf-anzahl { margin: 0; }
.wf-slug { font-size: var(--fs-sm); overflow-wrap: anywhere; }
.wf-mail { overflow-wrap: anywhere; }
.wf-formular { display: grid; grid-template-columns: minmax(0, 1fr); gap: var(--sp-3); min-width: 0; }
</style>
