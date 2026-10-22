<template>
  <div class="dk-screen dk-screen-enter">
    <div class="dk-screen-header">
      <div>
        <h1 class="dk-screen-title">Meine Dienste</h1>
        <p class="dk-screen-sub">Deine Zuordnungen aus den veröffentlichten Plänen</p>
      </div>
      <div class="dk-screen-actions">
        <a class="dk-btn dk-btn-secondary dk-btn-sm" href="#/planrahmen">Zur Planübersicht</a>
      </div>
    </div>

    <div v-if="laden" class="pr-md-zustand">Lade Dienste …</div>

    <div v-else-if="seitenFehler.length" class="pr-md-zustand pr-md-zustand--fehler">
      <PrMeldungen :meldungen="seitenFehler" />
      <button type="button" class="dk-btn dk-btn-secondary dk-btn-sm" @click="ladenAlles">Nochmal</button>
    </div>

    <template v-else>
      <div v-if="!gruppen.length" class="dk-empty">
        <p class="dk-empty-desc">
          Dir sind derzeit in keinem veröffentlichten Plan Dienste zugewiesen.
        </p>
      </div>

      <section v-for="g in gruppen" :key="g.name" class="pr-md-gruppe">
        <h2 class="pr-md-gruppe-titel">
          {{ g.name }}
          <a v-if="g.plan" class="pr-md-planlink" :href="planLink(g)">Plan öffnen</a>
        </h2>
        <!-- OP-HANDY-6: „geändert am“-Marker — der Planer sieht, wann zuletzt
             veroeffentlicht wurde; das nimmt die Frage „gilt das noch?“ heraus. -->
        <p v-if="geaendertText(g)" class="pr-md-stand">
          Stand: {{ geaendertText(g) }}
        </p>
        <div class="dk-list">
          <div
            v-for="(d, i) in g.dienste"
            :key="kennung(d, i)"
            class="dk-list-item pr-md-zeile"
            :class="{ 'pr-md-zeile--konflikt': d.abwesend }"
          >
            <div class="pr-md-zeile-kopf">
              <span class="pr-md-datum">{{ datumText(d.termin) }}</span>
              <span v-if="d.uhrzeit" class="pr-md-uhrzeit">{{ uhrzeitText(d.uhrzeit) }}</span>
              <span v-if="d.lied_titel" class="pr-md-lied">{{ d.lied_titel }}</span>
            </div>
            <div class="pr-md-zeile-rolle">
              <span class="pr-md-feld">{{ feldName(d.feld_pfad) }}</span>
              <span v-if="d.anlass" class="pr-md-anlass">{{ d.anlass }}</span>
              <span v-if="d.termin_titel" class="pr-md-anlass">{{ d.termin_titel }}</span>
            </div>
            <div v-if="d.mitwirkende && d.mitwirkende.length" class="pr-md-mitwirkende">
              {{ mitwirkendeText(d.mitwirkende) }}
            </div>
            <div v-if="d.abwesend" class="pr-md-konflikt">
              ⚠️ Du hast für diesen Tag eine Abwesenheit gemeldet — bitte kläre die Einteilung.
            </div>
            <div class="pr-md-zeile-aktionen">
              <button
                type="button" class="dk-btn dk-btn-ghost dk-btn-sm"
                :disabled="absageLaeuft[d.feld_pfad]"
                @click="absageAnfragen(d, g)"
              >{{ absageLaeuft[d.feld_pfad] ? 'Wird abgesagt …' : 'Absagen' }}</button>
            </div>
          </div>
        </div>
      </section>

      <!-- UXP-R17: gemeldete Abwesenheiten — nach dem Neuladen sichtbar, loeschbar. -->
      <section class="dk-card pr-md-abwesenheit">
        <h2 class="pr-md-gruppe-titel">Abwesenheiten</h2>
        <p class="pr-md-hinweis">
          Melde deine Abwesenheit für einen Zeitraum — bei der Planung werden
          Abwesende kommen beim automatischen Einteilen nicht mehr in die Auswahl.
        </p>

        <div v-if="abwFehler.length" class="pr-md-block">
          <PrMeldungen :meldungen="abwFehler" />
        </div>

        <div v-if="!eigeneKennung" class="pr-md-hinweis">
          Deinem Konto ist kein Mitglied zugeordnet — bitte wende dich an die Kirchenverwaltung.
        </div>

        <template v-else>
          <p>* = Pflichtfeld</p>
          <div class="dk-form-grid">
            <div class="dk-form-group">
              <label for="pr-md-von">Abwesend von *</label>
              <p v-if="feldFehler['pr-md-von']" id="pr-md-von-fehler" role="alert" class="dk-form-error">{{ feldFehler['pr-md-von'] }}</p>
              <input id="pr-md-von" :aria-invalid="!!feldFehler['pr-md-von']" :aria-describedby="feldFehler['pr-md-von'] ? 'pr-md-von-fehler' : undefined" v-model="abwVon" type="date" class="dk-form-input" />
            </div>
            <div class="dk-form-group">
              <label for="pr-md-bis">Abwesend bis *</label>
              <p v-if="feldFehler['pr-md-bis']" id="pr-md-bis-fehler" role="alert" class="dk-form-error">{{ feldFehler['pr-md-bis'] }}</p>
              <input id="pr-md-bis" :aria-invalid="!!feldFehler['pr-md-bis']" :aria-describedby="feldFehler['pr-md-bis'] ? 'pr-md-bis-fehler' : undefined" v-model="abwBis" type="date" class="dk-form-input" />
            </div>
          </div>
          <div class="dk-form-group">
            <label for="pr-md-grund">Grund (freiwillig)</label>
            <input id="pr-md-grund" v-model="abwGrund" type="text" class="dk-form-input" placeholder="z. B. Urlaub" />
          </div>
          <button
            type="button" class="dk-btn dk-btn-primary dk-btn-sm"
            :disabled="abwSpeichert"
            @click="abwesenheitMeldenAktion"
          >{{ abwSpeichert ? 'Wird gemeldet …' : 'Abwesenheit melden' }}</button>
        </template>

        <div v-if="abwLaden" class="pr-md-hinweis pr-md-gemeldet-laden">Lade Abwesenheiten …</div>
        <ul v-else-if="abwGemeldet.length" class="pr-md-gemeldet">
          <li v-for="a in abwGemeldet" :key="a.id" class="pr-md-gemeldet-zeile">
            <span>
              {{ datumText(a.von, false) }} – {{ datumText(a.bis, false) }}
              <span v-if="a.grund"> · {{ a.grund }}</span>
            </span>
            <button
              type="button" class="dk-btn dk-btn-ghost dk-btn-sm"
              :disabled="abwLoescht[a.id]"
              @click="abwesenheitLoeschenAktion(a)"
            >{{ abwLoescht[a.id] ? 'Wird gelöscht …' : 'Löschen' }}</button>
          </li>
        </ul>
        <p v-else-if="eigeneKennung" class="pr-md-hinweis pr-md-keine-abw">
          Du hast keine Abwesenheit gemeldet.
        </p>
      </section>
    </template>

    <!-- Absage bestätigen: der Platz wird frei, der Planer sieht es im Verlauf. -->
    <DkModal variant="planrahmen" v-model="absageOffen" title="Einteilung absagen">
      <p class="pr-md-modaltext" v-if="absageZiel">
        <strong>{{ absageZiel.lied_titel || feldName(absageZiel) }}</strong><br />
        {{ datumText(absageZiel.termin) }}<span v-if="absageZiel.uhrzeit">, {{ uhrzeitText(absageZiel.uhrzeit) }}</span>
      </p>
      <p class="pr-md-hinweis">
        Mit dem Absagen gibst du deinen Platz frei. Die Planerin/der Planer sieht
        die Absage und kann den Platz neu besetzen.
      </p>
      <div v-if="absageFehler.length" class="pr-md-block">
        <PrMeldungen :meldungen="absageFehler" />
      </div>
      <template #footer>
        <button type="button" class="dk-btn dk-btn-ghost" @click="absageOffen = false">Zurück</button>
        <button type="button" class="dk-btn dk-btn-primary" :disabled="absageSpeichert" @click="absageAusfuehren">
          {{ absageSpeichert ? 'Wird abgesagt …' : 'Jetzt absagen' }}
        </button>
      </template>
    </DkModal>
  </div>
</template>

<script setup>
/**
 * Personensicht des Plan-Rahmens: eigene Zuordnungen aus den
 * veröffentlichten Snapshots (meine_dienste) mit Lied, Uhrzeit und
 * Mitwirkenden (OP-CHOR-7), Konflikthinweis bei Abwesenheit und Absage
 * (OP-HANDY-18) sowie Abwesenheitsliste mit Löschen (UXP-R17).
 * Kein eigener Speicherweg — alles über die geprüfte API.
 */
import { ref, computed, onMounted } from 'vue'
import { usePlanrahmen, datumText, uhrzeitText, wertText, fehlerMeldungen } from '../../composables/usePlanrahmen.js'
import { useSession } from '../../composables/useSession.js'
import { showToast } from '../../composables/useToast.js'
import { pflichtFehler, erstesFehlerfeld } from '../../composables/formularPruefung.mjs'
import DkModal from '../../components/DkModal.vue'
import PrMeldungen from '../../components/planrahmen/PrMeldungen.vue'
import { feldName, mitwirkendeText } from '../../components/planrahmen/meine-dienste.mjs'

const { meineDienste, abwesenheitMelden, abwesenheitenListe, abwesenheitLoeschen, dienstAbsagen } = usePlanrahmen()
const { mitglied } = useSession()

const laden = ref(true)
const seitenFehler = ref([])
const dienste = ref([])

const abwVon = ref('')
const abwBis = ref('')
const abwGrund = ref('')
const abwSpeichert = ref(false)
const abwFehler = ref([])
const feldFehler = ref({})
const abwGemeldet = ref([])
const abwLaden = ref(true)
const abwLoescht = ref({})

const eigeneKennung = computed(() => mitglied.value?.name || '')

async function ladenAlles() {
    laden.value = true
    seitenFehler.value = []
    try {
        const liste = await meineDienste()
        const heute = new Date().toLocaleDateString('sv-SE')
        dienste.value = Array.isArray(liste) ? liste.filter(d => d.termin >= heute) : []
    } catch (err) {
        dienste.value = []
        seitenFehler.value = fehlerMeldungen(err)
    } finally {
        laden.value = false
    }
}

onMounted(() => {
    ladenAlles()
    abwesenheitenLaden()
})

// ── Dienste nach Plan gruppieren ───────────────────────────────────────────

const gruppen = computed(() => {
    const karte = new Map()
    for (const d of dienste.value) {
        const key = d.plan || d.titel || ''
        if (!karte.has(key)) karte.set(key, { plan: d.plan || '', name: d.titel || 'Plan', dienste: [] })
        karte.get(key).dienste.push(d)
    }
    return [...karte.values()].map((g) => ({
        ...g,
        dienste: g.dienste.slice().sort((a, b) => String(a.termin || '').localeCompare(String(b.termin || ''))),
    })).sort((a, b) => (a.dienste[0]?.termin || '').localeCompare(b.dienste[0]?.termin || ''))
})

function kennung(d, i) {
    return `${d.plan || ''}-${d.termin_id || d.termin || ''}-${d.feld_pfad || ''}-${i}`
}

/** OP-HANDY-5: direkter Sprung zum Plan (Terminwahl in der Planansicht). */
function planLink(g) {
    return '#/planrahmen/plan/' + encodeURIComponent(g.plan)
}

/**
 * OP-HANDY-6: „geändert am“-Marker. Der veroeffentlichte Stand traegt den
 * Zeitpunkt seiner Veroeffentlichung (`plan_geaendert`); daraus wird eine
 * verstaendliche Zeile. Ohne Angabe bleibt die Zeile aus.
 */
function geaendertText(g) {
    const iso = g.dienste.find(d => d.plan_geaendert)?.plan_geaendert
    if (!iso) return ''
    const d = new Date(String(iso).replace(' ', 'T'))
    if (Number.isNaN(d.getTime())) return ''
    return 'zuletzt geändert am ' + d.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric' })
}

// ── Absage (OP-HANDY-18) ───────────────────────────────────────────────────

const absageOffen = ref(false)
const absageZiel = ref(null)
const absageGruppe = ref(null)
const absageSpeichert = ref(false)
const absageFehler = ref([])
const absageLaeuft = ref({})

function absageAnfragen(d, g) {
    absageZiel.value = d
    absageGruppe.value = g
    absageFehler.value = []
    absageOffen.value = true
}

async function absageAusfuehren() {
    const d = absageZiel.value
    if (!d || absageSpeichert.value) return
    absageSpeichert.value = true
    absageLaeuft.value = { ...absageLaeuft.value, [d.feld_pfad]: true }
    absageFehler.value = []
    try {
        await dienstAbsagen(d.plan, d.termin_id, d.feld_pfad)
        showToast('Einteilung abgesagt — der Platz ist wieder frei.')
        absageOffen.value = false
        await ladenAlles()
    } catch (err) {
        absageFehler.value = fehlerMeldungen(err)
    } finally {
        absageSpeichert.value = false
        absageLaeuft.value = { ...absageLaeuft.value, [d.feld_pfad]: false }
    }
}

// ── Abwesenheit (UXP-R17) ──────────────────────────────────────────────────


async function abwesenheitenLaden() {
    abwLaden.value = true
    try {
        const liste = await abwesenheitenListe()
        abwGemeldet.value = Array.isArray(liste) ? liste : []
    } catch {
        // Lesefehler darf die Dienstliste nicht kippen: leere Liste zeigen.
        abwGemeldet.value = []
    } finally {
        abwLaden.value = false
    }
}

async function abwesenheitMeldenAktion() {
    if (abwSpeichert.value || !eigeneKennung.value) return
    feldFehler.value = pflichtFehler([
        ['pr-md-von', abwVon.value, 'den Beginn'],
        ['pr-md-bis', abwBis.value, 'das Ende'],
    ])
    if (abwVon.value && abwBis.value && abwBis.value < abwVon.value) {
        feldFehler.value['pr-md-bis'] = 'Das Ende darf nicht vor dem Beginn liegen.'
    }
    if (Object.keys(feldFehler.value).length) {
        erstesFehlerfeld(feldFehler.value)
        return
    }
    abwSpeichert.value = true
    abwFehler.value = []
    try {
        await abwesenheitMelden(eigeneKennung.value, abwVon.value, abwBis.value, abwGrund.value.trim())
        abwVon.value = ''
        abwBis.value = ''
        abwGrund.value = ''
        showToast('Abwesenheit gemeldet.')
        await abwesenheitenLaden()
        await ladenAlles()   // Konflikthinweis an den Diensten aktualisieren
    } catch (err) {
        abwFehler.value = fehlerMeldungen(err)
    } finally {
        abwSpeichert.value = false
    }
}

async function abwesenheitLoeschenAktion(a) {
    if (!a?.id || abwLoescht.value[a.id]) return
    abwLoescht.value = { ...abwLoescht.value, [a.id]: true }
    abwFehler.value = []
    try {
        await abwesenheitLoeschen(a.id)
        showToast('Abwesenheit gelöscht.')
        abwGemeldet.value = abwGemeldet.value.filter((x) => x.id !== a.id)
        await ladenAlles()
    } catch (err) {
        abwFehler.value = fehlerMeldungen(err)
    } finally {
        abwLoescht.value = { ...abwLoescht.value, [a.id]: false }
    }
}
</script>

<style scoped>
.dk-form-error { color: var(--err); font-size: var(--fs-sm); margin: 0; }
.pr-md-zustand { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; color: var(--dk-text-muted); font-size: 0.9rem; }
.pr-md-zustand--fehler { color: var(--dk-danger); }
.pr-md-gruppe + .pr-md-gruppe { margin-top: 24px; }
.pr-md-gruppe-titel {
  display: flex; align-items: baseline; gap: 10px;
  font-size: 0.76rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em;
  color: var(--dk-text-muted); margin: 0 0 10px;
}
.pr-md-planlink { font-size: 0.72rem; text-transform: none; letter-spacing: 0; color: var(--dk-brand-700, var(--dk-info)); }
.pr-md-stand { font-size: 0.72rem; color: var(--dk-text-muted); margin: -6px 0 10px; }
.pr-md-zeile { display: flex; flex-direction: column; gap: 4px; align-items: stretch; }
.pr-md-zeile--konflikt { border-left: 3px solid var(--dk-warning); padding-left: 10px; }
.pr-md-zeile-kopf { display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap; }
.pr-md-datum { font-size: 0.86rem; font-weight: 600; color: var(--dk-text); }
.pr-md-uhrzeit { font-size: 0.8rem; color: var(--dk-text-muted); }
.pr-md-lied { font-size: 0.88rem; color: var(--dk-text); }
.pr-md-zeile-rolle { display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap; }
.pr-md-feld { font-size: 0.8rem; color: var(--dk-text-muted); }
.pr-md-anlass { font-size: 0.78rem; color: var(--dk-text-subtle); }
.pr-md-mitwirkende { font-size: 0.8rem; color: var(--dk-text-muted); }
.pr-md-konflikt { font-size: 0.8rem; color: var(--dk-warning); }
.pr-md-zeile-aktionen { display: flex; gap: 8px; margin-top: 2px; }
.pr-md-abwesenheit { padding: 18px 20px; margin-top: 28px; }
.pr-md-hinweis { font-size: 0.84rem; color: var(--dk-text-muted); margin: 0 0 12px; }
.pr-md-block { margin-bottom: 10px; }
.pr-md-modaltext { font-size: 0.9rem; color: var(--dk-text); margin: 0 0 8px; }
.pr-md-gemeldet { list-style: none; margin: 14px 0 0; padding: 0; display: flex; flex-direction: column; gap: 6px; font-size: 0.84rem; color: var(--dk-text); }
.pr-md-gemeldet-zeile { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; border-bottom: 1px solid var(--dk-divider); padding-bottom: 6px; }
.pr-md-keine-abw { margin-top: 14px; }
</style>
