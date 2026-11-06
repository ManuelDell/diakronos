<template>
  <div class="dk-screen dk-screen-enter">
    <!-- UX3c: Die Reiterzeile zeichnet der Rahmen (pages/dienste/Bereich.vue) —
         EINE Stelle für alle drei Reiter, damit sie beim Wechsel stehen bleibt. -->
    <div class="dk-screen-header">
      <div>
        <h1 class="dk-screen-title">Meine Dienste</h1>
        <p class="dk-screen-sub">Deine Zuordnungen aus den veröffentlichten Plänen</p>
      </div>
      <div class="dk-screen-actions">
        <a class="dk-btn dk-btn-secondary dk-btn-sm" href="#/dienste/dienstplaene">Zu den Dienstplänen</a>
      </div>
    </div>

    <!-- UX2d3a: Laden zeigt den Umriss (Skelett, erst nach 300 ms), keinen Satz. -->
    <DkSkelett v-if="skelettSichtbar" form="zeilen" :anzahl="6" text="Dienste werden geladen …" />

    <div v-else-if="seitenFehler.length" class="pr-md-zustand pr-md-zustand--fehler">
      <PrMeldungen :meldungen="seitenFehler" />
      <button type="button" class="dk-btn dk-btn-secondary dk-btn-sm" @click="ladenAlles">Erneut versuchen</button>
    </div>

    <template v-else>
      <div v-if="!gruppen.length" class="dk-empty">
        <p class="dk-empty-desc">
          Dir sind derzeit in keinem veröffentlichten Plan Dienste zugewiesen.
        </p>
      </div>

      <template v-else>
        <!-- UX-B2: Legende der Rollenfarben. Sie zeigt nur Rollen, die in den
             angezeigten Diensten wirklich vorkommen — Buchstabe UND Klartext,
             damit die Farbe nicht das einzige Unterscheidungsmittel ist. -->
        <ul v-if="legendeEintraege.length" class="pr-md-legende" aria-label="Rollen">
          <li class="pr-md-legende-titel">Rollen</li>
          <li
            v-for="e in legendeEintraege"
            :key="e.rolle"
            class="pr-md-legende-punkt"
            :data-art="e.farbe"
          >
            <span class="pr-md-rolle-zeichen" :data-art="e.farbe" aria-hidden="true">{{ e.zeichen }}</span>
            {{ e.text }}
          </li>
        </ul>

        <!-- UX-B2: Plan-Kopf (Titel, Plan öffnen, Stand) einmal je Plan. -->
        <div v-for="g in gruppen" :key="g.name" class="pr-md-plan">
          <div class="pr-md-plan-kopf">
            <h2 class="pr-md-gruppe-titel">{{ g.name }}</h2>
            <a v-if="g.plan" class="pr-md-planlink" :href="planLink(g)">Plan öffnen</a>
            <!-- OP-HANDY-6: „geändert am“-Marker — der Planer sieht, wann zuletzt
                 veroeffentlicht wurde; das nimmt die Frage „gilt das noch?“ heraus. -->
            <span v-if="geaendertText(g)" class="pr-md-stand">Stand: {{ geaendertText(g) }}</span>
          </div>

          <div class="pr-md-monate">
            <section v-for="m in g.monate" :key="m.schluessel" class="dk-card pr-md-monat">
              <header class="pr-md-monat-kopf">
                <h3 class="pr-md-monat-titel">{{ m.titel }}</h3>
                <span class="dk-badge">{{ diensteText(m.dienste.length) }}</span>
              </header>
              <ul class="pr-md-monat-liste">
                <li
                  v-for="(d, i) in m.dienste"
                  :key="kennung(d, i)"
                  class="pr-md-monat-zeile"
                  :class="{ 'pr-md-monat-zeile--konflikt': d.abwesend }"
                >
                  <span
                    class="pr-md-rolle-zeichen"
                    :data-art="rollenFarbe(d.feld_pfad || d.feld_name)"
                    :title="feldName(d.feld_pfad)"
                    :aria-label="feldName(d.feld_pfad)"
                  >{{ rollenZeichen(d.feld_pfad || d.feld_name, feldName(d.feld_pfad)) }}</span>
                  <div class="pr-md-monat-haupt">
                    <p class="pr-md-monat-kopfzeile">
                      <span class="pr-md-datum">{{ datumText(d.termin) }}</span>
                      <span v-if="d.uhrzeit" class="pr-md-uhrzeit">{{ uhrzeitText(d.uhrzeit) }}</span>
                      <span class="pr-md-feld">{{ feldName(d.feld_pfad) }}</span>
                    </p>
                    <p v-if="d.lied_titel" class="pr-md-lied">{{ d.lied_titel }}</p>
                    <p v-if="d.anlass || d.termin_titel" class="pr-md-anlass">
                      {{ [d.anlass, d.termin_titel].filter(Boolean).join(' · ') }}
                    </p>
                    <p v-if="d.mitwirkende && d.mitwirkende.length" class="pr-md-mitwirkende">
                      {{ mitwirkendeText(d.mitwirkende) }}
                    </p>
                    <p v-if="d.abwesend" class="pr-md-konflikt">
                      ⚠️ Du hast für diesen Tag eine Abwesenheit gemeldet — bitte kläre die Einteilung.
                    </p>
                  </div>
                  <div class="pr-md-monat-aktion">
                    <button
                      type="button" class="dk-btn dk-btn-ghost dk-btn-sm"
                      :disabled="absageLaeuft[d.feld_pfad]"
                      @click="absageAnfragen(d, g)"
                    >{{ absageLaeuft[d.feld_pfad] ? 'Wird abgesagt …' : 'Absagen' }}</button>
                  </div>
                </li>
              </ul>
            </section>
          </div>
        </div>
      </template>


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

        <DkSkelett v-if="abwSkelettSichtbar" kurz form="zeilen" :anzahl="2" text="Abwesenheiten werden geladen …" />
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
// UX3c: Reiterzeile und aktiver Reiter kommen aus dem Rahmen
// (pages/dienste/Bereich.vue) — die Seite selbst kennt nur ihren Inhalt.
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
import DkSkelett from '../../components/ui/DkSkelett.vue'
import { useLadeSkelett } from '../../composables/useLadeSkelett.js'
import PrMeldungen from '../../components/planrahmen/PrMeldungen.vue'
import { feldName, mitwirkendeText } from '../../components/planrahmen/meine-dienste.mjs'
import {
    monatsGruppen, rollenFarbe, rollenZeichen, legende, diensteText,
} from '../../components/planrahmen/meine-dienste-monate.mjs'

const { meineDienste, abwesenheitMelden, abwesenheitenListe, abwesenheitLoeschen, dienstAbsagen } = usePlanrahmen()
const { mitglied } = useSession()

const laden = ref(true)
// UX2d3a: Platzhalter erst, wenn das Laden merklich dauert (300 ms).
const { skelettSichtbar } = useLadeSkelett(laden)
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
// UX2d3a: eigener Platzhalter für die Abwesenheitsliste (gleiche 300-ms-Regel).
const { skelettSichtbar: abwSkelettSichtbar } = useLadeSkelett(abwLaden)
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

// ── Dienste nach Plan, darin je Monat eine Karte (UX-B2) ───────────────────

const gruppen = computed(() => {
    const karte = new Map()
    for (const d of dienste.value) {
        const key = d.plan || d.titel || ''
        if (!karte.has(key)) karte.set(key, { plan: d.plan || '', name: d.titel || 'Plan', dienste: [] })
        karte.get(key).dienste.push(d)
    }
    return [...karte.values()].map((g) => {
        const sortiert = g.dienste.slice().sort((a, b) => String(a.termin || '').localeCompare(String(b.termin || '')))
        // Eine Karte je Monat; `dienste` bleibt fuer die Absage-/Stand-Logik
        // erhalten (geaendertText liest daraus), `monate` traegt die Karten.
        return { ...g, dienste: sortiert, monate: monatsGruppen(sortiert) }
    }).sort((a, b) => (a.dienste[0]?.termin || '').localeCompare(b.dienste[0]?.termin || ''))
})

/** Legende: nur Rollen, die in den angezeigten Diensten vorkommen. */
const legendeEintraege = computed(() => legende(dienste.value, (rolle) => feldName(rolle)))

function kennung(d, i) {
    return `${d.plan || ''}-${d.termin_id || d.termin || ''}-${d.feld_pfad || ''}-${i}`
}

/** OP-HANDY-5: direkter Sprung zum Plan (Terminwahl in der Planansicht). */
function planLink(g) {
    return '#/dienste/dienstplaene/plan/' + encodeURIComponent(g.plan)
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
.pr-md-zustand { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; color: var(--dk-text-muted); font-size: var(--fs-14); }
.pr-md-zustand--fehler { color: var(--dk-danger); }
.pr-md-gruppe + .pr-md-gruppe { margin-top: 24px; }
.pr-md-plan + .pr-md-plan { margin-top: 28px; }
.pr-md-plan-kopf { display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; margin: 0 0 12px; }
.pr-md-gruppe-titel {
  display: flex; align-items: baseline; gap: 10px;
  font-size: var(--fs-12); font-weight: var(--fw-fett); text-transform: uppercase; letter-spacing: 0.05em;
  color: var(--dk-text-muted); margin: 0;
}
.pr-md-planlink { font-size: var(--fs-12); text-transform: none; letter-spacing: 0; color: var(--dk-brand-700, var(--dk-info)); }
.pr-md-stand { font-size: var(--fs-12); color: var(--dk-text-muted); margin: 0; }

/* ── UX-B2/B2b: Monatskarten mit Rollenfarbe ──────────────────────────────
   Je Monat eine Karte (dk-card), darin eine Zeile je Dienst mit farbigem
   Rollenzeichen. Die Zeichen tragen IMMER einen Buchstaben — die Farbe ist
   nie das einzige Unterscheidungsmittel (WCAG 1.4.1).

   Variante D (Operator-Entscheidung 2026-10-24): FLÄCHE = Rollenton 12 %
   (hell) / 22 % (dunkel) ueber der Kartenfläche, SCHRIFT einheitlich --text.
   Kein einziger Farbwert steht hier fest — die Töne kommen aus den Tokens
   --accent, --info, --ok, --muted; die Deckkraft aus FLAECHE_HELL/FLAECHE_DUNKEL. */
.pr-md-legende {
  display: flex; align-items: center; gap: 14px; flex-wrap: wrap;
  list-style: none; margin: 0 0 20px; padding: 10px 14px;
  border: 1px solid var(--dk-border); border-radius: var(--radius);
  background: var(--dk-surface-2);
}
.pr-md-legende-titel {
  font-size: var(--fs-12); font-weight: var(--fw-fett); text-transform: uppercase; letter-spacing: 0.05em;
  color: var(--dk-text-muted);
}
.pr-md-legende-punkt {
  display: inline-flex; align-items: center; gap: 7px;
  font-size: var(--fs-14); color: var(--dk-text);
}
.pr-md-rolle-zeichen {
  display: inline-flex; align-items: center; justify-content: center;
  width: 26px; height: 26px; flex: 0 0 26px;
  border-radius: var(--radius-sm);
  font-size: var(--fs-12); font-weight: var(--fw-fett); line-height: 1;
  /* Rueckfall (unbekannte Rolle): Fläche ohne Rollenton, nur Rahmen. */
  background: transparent; color: var(--dk-text);
  border: 1px solid var(--dk-border-strong);
}
.pr-md-rolle-zeichen[data-art="accent"],
.pr-md-rolle-zeichen[data-art="info"],
.pr-md-rolle-zeichen[data-art="ok"],
.pr-md-rolle-zeichen[data-art="warm-500"] {
  background: color-mix(in srgb, var(--rolle-ton) var(--rolle-flaeche), var(--surface));
  color: var(--text);
  border-color: color-mix(in srgb, var(--rolle-ton) 35%, var(--line));
}
/* Der Ton je Rolle — nur vorhandene Tokens, kein neuer Farbwert. */
.pr-md-rolle-zeichen[data-art="accent"]   { --rolle-ton: var(--accent); }
.pr-md-rolle-zeichen[data-art="info"]     { --rolle-ton: var(--info); }
.pr-md-rolle-zeichen[data-art="ok"]       { --rolle-ton: var(--ok); }
/* Einsingen: neutral (warmgrau) statt --warn. Im Dunkelmodus liegen --accent
   und --warn auf demselben Farbton. `--muted` ist dort zu blau und rueckt bei
   22 % an --info heran; `--dk-warm-500` (Rohwert, themenunabhaengig) haelt zu
   allen drei anderen Rollen sichtbaren Abstand. */
.pr-md-rolle-zeichen[data-art="warm-500"] { --rolle-ton: var(--dk-warm-500); }

/* Deckkraft der Fläche: hell 12 %, dunkel 22 % (dort verschwinden 12 %).
   Gesetzt an den beiden Stellen, die ein Rollenzeichen tragen (Legende und
   Dienstzeile) — nicht an einem Sammel-Selektor, den es im DOM nicht gibt. */
.pr-md-legende,
.pr-md-monat-zeile { --rolle-flaeche: 12%; }
[data-theme="dark"] .pr-md-legende,
[data-theme="dark"] .pr-md-monat-zeile,
:root[data-theme="dark"] .pr-md-legende,
:root[data-theme="dark"] .pr-md-monat-zeile { --rolle-flaeche: 22%; }

.pr-md-monate { display: flex; flex-direction: column; gap: 14px; }
.pr-md-monat { overflow: hidden; }
.pr-md-monat-kopf {
  display: flex; align-items: center; justify-content: space-between; gap: 12px;
  padding: 12px 16px; border-bottom: 1px solid var(--dk-divider);
  background: var(--dk-surface-2);
}
.pr-md-monat-titel {
  font-size: var(--fs-16); font-weight: var(--fw-fett); color: var(--dk-text); margin: 0;
  letter-spacing: 0.01em;
}
.pr-md-monat-liste { list-style: none; margin: 0; padding: 0; }
.pr-md-monat-zeile {
  display: flex; align-items: flex-start; gap: 12px;
  padding: 12px 16px; border-bottom: 1px solid var(--dk-divider);
}
.pr-md-monat-zeile:last-child { border-bottom: none; }
.pr-md-monat-zeile:hover { background: var(--dk-surface-hover); }
.pr-md-monat-zeile--konflikt { border-left: 3px solid var(--dk-warning); padding-left: 13px; }
.pr-md-monat-haupt { flex: 1 1 auto; min-width: 0; display: flex; flex-direction: column; gap: 3px; }
.pr-md-monat-haupt > p { margin: 0; }
.pr-md-monat-kopfzeile { display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; }
.pr-md-monat-aktion { flex: 0 0 auto; }
.pr-md-zeile { display: flex; flex-direction: column; gap: 4px; align-items: stretch; }
.pr-md-zeile--konflikt { border-left: 3px solid var(--dk-warning); padding-left: 10px; }
.pr-md-zeile-kopf { display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap; }
.pr-md-datum { font-size: var(--fs-14); font-weight: var(--fw-fett); color: var(--dk-text); }
.pr-md-uhrzeit { font-size: var(--fs-12); color: var(--dk-text-muted); }
.pr-md-lied { font-size: var(--fs-14); color: var(--dk-text); }
.pr-md-zeile-rolle { display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap; }
.pr-md-feld { font-size: var(--fs-12); color: var(--dk-text-muted); }
.pr-md-anlass { font-size: var(--fs-12); color: var(--dk-text-subtle); }
.pr-md-mitwirkende { font-size: var(--fs-12); color: var(--dk-text-muted); }
.pr-md-konflikt { font-size: var(--fs-12); color: var(--dk-warning); }
.pr-md-zeile-aktionen { display: flex; gap: 8px; margin-top: 2px; }

/* Mobil: die Absage-Aktion rueckt unter den Text, das Rollenzeichen bleibt
   links in der Zeile — die Monatskarten bleiben so auch auf 390 px lesbar. */
/* FIX-6: Mobil-Umschaltung — LAYOUT, also nur die Breite (index.css
   «FIX-6 · Layout nur nach Breite», dieselbe Grenze 720 px).
   Runde 2 (Messung t_fba1a868): Der Umbruch braucht im Mobil-Layout
   100 % Breite. `.pr-md-monat-haupt { flex: 1 1 auto }` behielt sonst seine
   Inhaltsbreite (278 px) und `flex-wrap: wrap` hatte nichts umzubrechen — die
   Absage-Aktion rutschte NICHT unter den Text, sondern blieb in der Zeile
   daneben. Desktop unverändert (Regel gilt nur <= 720 px). */
@media (max-width: 720px) {
  .pr-md-legende { gap: 10px 14px; padding: 10px 12px; }
  .pr-md-monat-zeile { flex-wrap: wrap; padding: 12px; }
  .pr-md-monat-haupt { flex: 1 1 100%; }
  .pr-md-monat-aktion { margin-left: 38px; }
  .pr-md-monat-kopf { padding: 10px 12px; }
}
.pr-md-abwesenheit { padding: 18px 20px; margin-top: 28px; }
.pr-md-hinweis { font-size: var(--fs-14); color: var(--dk-text-muted); margin: 0 0 12px; }
.pr-md-block { margin-bottom: 10px; }
.pr-md-modaltext { font-size: var(--fs-14); color: var(--dk-text); margin: 0 0 8px; }
.pr-md-gemeldet { list-style: none; margin: 14px 0 0; padding: 0; display: flex; flex-direction: column; gap: 6px; font-size: var(--fs-14); color: var(--dk-text); }
.pr-md-gemeldet-zeile { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; border-bottom: 1px solid var(--dk-divider); padding-bottom: 6px; }
.pr-md-keine-abw { margin-top: 14px; }
</style>
