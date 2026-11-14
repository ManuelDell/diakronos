<template>
  <div class="rr-abschnitt">
    <h2>Rollen &amp; Rechte</h2>
    <p>Hier siehst du, wer welche Rolle hat. Rollen bestimmen, was jemand darf —
      Verantwortliche bestimmen zusätzlich, wer einen Bereich oder eine Gruppe
      pflegen darf.</p>

    <DkSkelett v-if="laedt" form="zeilen" :anzahl="6" text="Übersicht wird geladen …" />
    <DkHint v-if="fehler" variant="err" role="alert">{{ fehler }}</DkHint>
    <DkButton v-if="!geladen && !laedt" variant="secondary" @click="laden">Erneut versuchen</DkButton>
    <DkErfolgsmeldung :text="erfolg" />

    <template v-if="geladen">
      <!-- ── Rollen je Person ───────────────────────────────────────────── -->
      <DkCard title="Wer hat welche Rolle">
        <p class="rr-hilfe">Jede Person mit Zugang erscheint hier. Antippen öffnet die Rollenauswahl.
          Rollen mit Verwaltungsrechten darf nur ein System Manager vergeben oder entziehen.</p>

        <DkField label="Person suchen" :wert="suche" @update:wert="suche = $event" v-slot="feld">
          <input v-bind="feld.feldProps" class="dk-ui-eingabe" type="search"
            placeholder="Name oder E-Mail …" aria-label="Person suchen" />
        </DkField>

        <DkEmpty v-if="!gefiltert.length" title="Keine passende Person" icon="👤" />
        <ul v-else class="rr-liste">
          <li v-for="k in gefiltert" :key="k.user" class="rr-zeile">
            <div class="rr-person">
              <span class="rr-name">{{ k.anzeige }}</span>
              <span class="rr-unter">{{ k.email || k.user }}</span>
              <span v-if="!k.enabled" class="rr-schild rr-schild--gesperrt">Gesperrt</span>
              <span v-else-if="k.ausgeschlossen" class="rr-schild rr-schild--raus">Ausgeschlossen</span>
              <span v-if="k.hinweis" class="rr-hinweis">{{ k.hinweis }}</span>
            </div>
            <div class="rr-rollen">
              <span v-for="r in k.rollen" :key="r" class="rr-chip">{{ r }}</span>
              <span v-if="!k.rollen.length" class="rr-unter">Keine Rolle</span>
            </div>
            <DkButton variant="ghost" size="md" :disabled="!k.mitglied"
              :title="k.hinweis || (k.mitglied ? '' : 'Ohne Mitglied kann keine Rolle zugewiesen werden')"
              @click="bearbeiten(k)">Rollen ändern</DkButton>
          </li>
        </ul>
      </DkCard>

      <!-- ── Verantwortliche je Bereich/Gruppe ──────────────────────────── -->
      <DkCard title="Verantwortliche für Bereiche und Gruppen">
        <p class="rr-hilfe">Verantwortliche dürfen Pläne ihres Bereichs bzw. ihrer Gruppe
          anlegen und bearbeiten. Auswählbar sind nur Personen mit Zugang.</p>
        <DkField label="Bereich oder Gruppe wählen"
          :wert="bereich" @update:wert="bereich = $event" v-slot="feld">
          <select v-bind="feld.feldProps" class="dk-ui-eingabe">
            <option value="">Bitte wählen</option>
            <option v-for="b in bereiche" :key="b.id" :value="b.id">{{ b.label }}</option>
          </select>
        </DkField>

        <template v-if="bereich">
          <VerantwortlicheKarte :key="bereich" :doctype="gewaehlt.typ" :name="gewaehlt.name" />
        </template>
        <p v-else class="rr-unter">Noch kein Bereich gewählt.</p>
      </DkCard>
    </template>

    <!-- ── Rollenauswahl (Dialog) ───────────────────────────────────────── -->
    <DkDialog :model-value="!!dialog" :title="dialog ? `Rollen für ${dialog.anzeige}` : ''"
      :close-on-overlay="false" @update:model-value="schliesseDialog">
      <template v-if="dialog">
        <p class="rr-hilfe">Die Auswahl ersetzt die Rollen dieser Person. Rollen außerhalb
          dieser Liste (aus der Einrichtung) bleiben unberührt.</p>
        <ul class="rr-rollen-liste">
          <li v-for="r in rollenWaehlbar" :key="r" class="rr-rollen-zeile">
            <!-- UI-R8b: Checkbox + Rollenname + ⓘ stehen in EINER Zeile, das
                 Erklärfeld als EIGENE volle Zeile darunter (flex-wrap, das
                 Feld nimmt `flex-basis: 100%`). Es schwebt nicht: in einem
                 Dialog mit `overflow: auto` würde ein absolut gesetztes
                 Feld am Rand abgeschnitten und Querscrollen erzeugen. -->
            <label class="rr-rolle">
              <input type="checkbox" :value="r" v-model="gewaehlteRollen" />
              <span>{{ r }}</span>
            </label>
            <RrInfo :name="r" :erklaerung="erklaerungVon(r)" />
          </li>
        </ul>
        <DkHint v-if="!istSystemManager && beruehrtVerwaltung" variant="warn">
          Verwaltungsrollen kann nur ein System Manager vergeben oder entziehen.
        </DkHint>
        <DkHint v-if="dialogFehler" variant="err" role="alert">{{ dialogFehler }}</DkHint>
        <p v-if="ohneErklaerung.length" class="rr-unter">
          <template v-if="ohneErklaerung.length === 1">
            Für {{ ohneErklaerung[0] }} gibt es noch keine Erklärung —
            die Rolle gilt wie jede andere; beschrieben ist sie noch nicht.
          </template>
          <template v-else>
            Für {{ ohneErklaerung.join(', ') }} gibt es noch keine Erklärungen —
            die Rollen gelten wie jede andere; beschrieben sind sie noch nicht.
          </template>
        </p>
      </template>
      <template #footer>
        <DkButton variant="secondary" :disabled="speichert" @click="schliesseDialog(false)">Abbrechen</DkButton>
        <DkButton variant="primary" :loading="speichert" @click="speichern">Speichern</DkButton>
      </template>
    </DkDialog>
    <!-- ── Was bewirkt welche Rolle? (UI-R8) ────────────────────────────── -->
    <DkCard title="Was bewirkt welche Rolle?">
      <p class="rr-hilfe">
        Jede Rolle einmal erklärt — was sie darf und was nicht. Die Texte kommen
        aus derselben Quelle wie die Rechteprüfung; es gibt keine zweite Fassung.
      </p>

      <DkSkelett v-if="erklaerungLaedt" form="zeilen" :anzahl="4" text="Erklärungen werden geladen …" />
      <DkHint v-else-if="erklaerungFehler" variant="warn" role="status">
        {{ erklaerungFehler }}
      </DkHint>

      <template v-else-if="!erklaerung.leer">
        <div class="rr-gruppen">
        <section class="rr-gruppe" aria-labelledby="rr-gruppe-system">
          <h3 id="rr-gruppe-system" class="rr-gruppe-titel">Rollen im System</h3>
          <p v-if="erklaerung.einleitungen.systemrollen" class="rr-hilfe">
            {{ erklaerung.einleitungen.systemrollen }}
          </p>
          <dl class="rr-erklaerungen">
            <div v-for="e in erklaerung.systemrollen" :key="e.schluessel" class="rr-erklaerung">
              <dt class="rr-erklaerung-titel">{{ e.erklaerung.titel || e.schluessel }}</dt>
              <dd class="rr-erklaerung-text">
                <span class="rr-erklaerung-kurz">{{ e.erklaerung.kurz }}</span>
                <span v-if="e.schluessel !== (e.erklaerung.titel || e.schluessel)" class="rr-rollenname">
                  Rollenname: {{ e.schluessel }}
                </span>
                <span v-if="e.erklaerung.darf.length" class="rr-erklaerung-unter">Darf</span>
                <ul v-if="e.erklaerung.darf.length" class="rr-erklaerung-liste">
                  <li v-for="(punkt, i) in e.erklaerung.darf" :key="`d-${i}`">{{ punkt }}</li>
                </ul>
                <span v-if="e.erklaerung.darf_nicht.length" class="rr-erklaerung-unter">Darf nicht</span>
                <ul v-if="e.erklaerung.darf_nicht.length" class="rr-erklaerung-liste rr-erklaerung-liste--nein">
                  <li v-for="(punkt, i) in e.erklaerung.darf_nicht" :key="`n-${i}`">{{ punkt }}</li>
                </ul>
              </dd>
            </div>
          </dl>
        </section>

        <section v-if="erklaerung.gast" class="rr-gruppe" aria-labelledby="rr-gruppe-gast">
          <h3 id="rr-gruppe-gast" class="rr-gruppe-titel">Ohne Konto</h3>
          <p v-if="erklaerung.einleitungen.gast" class="rr-hilfe">
            {{ erklaerung.einleitungen.gast }}
          </p>
          <dl class="rr-erklaerungen">
            <div class="rr-erklaerung">
              <dt class="rr-erklaerung-titel">{{ erklaerung.gast.titel }}</dt>
              <dd class="rr-erklaerung-text">
                <span class="rr-erklaerung-kurz">{{ erklaerung.gast.kurz }}</span>
                <span v-if="erklaerung.gast.darf.length" class="rr-erklaerung-unter">Darf</span>
                <ul v-if="erklaerung.gast.darf.length" class="rr-erklaerung-liste">
                  <li v-for="(punkt, i) in erklaerung.gast.darf" :key="`gd-${i}`">{{ punkt }}</li>
                </ul>
                <span v-if="erklaerung.gast.darf_nicht.length" class="rr-erklaerung-unter">Darf nicht</span>
                <ul v-if="erklaerung.gast.darf_nicht.length" class="rr-erklaerung-liste rr-erklaerung-liste--nein">
                  <li v-for="(punkt, i) in erklaerung.gast.darf_nicht" :key="`gn-${i}`">{{ punkt }}</li>
                </ul>
              </dd>
            </div>
          </dl>
        </section>

        <section v-if="erklaerung.gruppenrollen.length" class="rr-gruppe" aria-labelledby="rr-gruppe-gruppen">
          <h3 id="rr-gruppe-gruppen" class="rr-gruppe-titel">Rollen in einer Gruppe</h3>
          <p v-if="erklaerung.einleitungen.gruppenrollen" class="rr-hilfe">
            {{ erklaerung.einleitungen.gruppenrollen }}
          </p>
          <dl class="rr-erklaerungen">
            <div v-for="e in erklaerung.gruppenrollen" :key="e.schluessel" class="rr-erklaerung">
              <dt class="rr-erklaerung-titel">{{ e.erklaerung.titel || e.schluessel }}</dt>
              <dd class="rr-erklaerung-text">
                <span class="rr-erklaerung-kurz">{{ e.erklaerung.kurz }}</span>
                <span v-if="e.erklaerung.darf.length" class="rr-erklaerung-unter">Darf</span>
                <ul v-if="e.erklaerung.darf.length" class="rr-erklaerung-liste">
                  <li v-for="(punkt, i) in e.erklaerung.darf" :key="`rd-${i}`">{{ punkt }}</li>
                </ul>
                <span v-if="e.erklaerung.darf_nicht.length" class="rr-erklaerung-unter">Darf nicht</span>
                <ul v-if="e.erklaerung.darf_nicht.length" class="rr-erklaerung-liste rr-erklaerung-liste--nein">
                  <li v-for="(punkt, i) in e.erklaerung.darf_nicht" :key="`rn-${i}`">{{ punkt }}</li>
                </ul>
              </dd>
            </div>
          </dl>
        </section>

        <section v-if="erklaerung.module.length" class="rr-gruppe" aria-labelledby="rr-gruppe-module">
          <h3 id="rr-gruppe-module" class="rr-gruppe-titel">Module</h3>
          <p v-if="erklaerung.einleitungen.module" class="rr-hilfe">
            {{ erklaerung.einleitungen.module }}
          </p>
          <dl class="rr-erklaerungen">
            <div v-for="m in erklaerung.module" :key="m.schluessel" class="rr-erklaerung">
              <dt class="rr-erklaerung-titel">{{ m.titel }}</dt>
              <dd class="rr-erklaerung-text">{{ m.text }}</dd>
            </div>
          </dl>
        </section>

        <section v-if="erklaerung.stufen.length" class="rr-gruppe" aria-labelledby="rr-gruppe-stufen">
          <h3 id="rr-gruppe-stufen" class="rr-gruppe-titel">Prüfstufen</h3>
          <p v-if="erklaerung.einleitungen.stufen" class="rr-hilfe">
            {{ erklaerung.einleitungen.stufen }}
          </p>
          <dl class="rr-erklaerungen">
            <div v-for="s in erklaerung.stufen" :key="s.schluessel" class="rr-erklaerung">
              <dt class="rr-erklaerung-titel">{{ s.titel }}</dt>
              <dd class="rr-erklaerung-text">{{ s.text }}</dd>
            </div>
          </dl>
        </section>
        </div>
      </template>
      <p v-else class="rr-unter">
        Der Server liefert gerade keine Erklärungen. Die Rollen gelten unverändert.
      </p>
    </DkCard>
  </div>
</template>

<script setup>
/**
 * N10 — Einstellungen-Abschnitt „Rollen & Rechte".
 *
 * Zeigt je Person mit Konto die Rollen und den Kontozustand (Lese-Tabelle) und
 * erlaubt das Aendern der Rollen. Zusaetzlich die Verantwortlichen je Bereich/
 * Gruppe (K1: auch Dienstbereiche) ueber die bestehende VerantwortlicheKarte.
 *
 * Die Rechte kommen vom Server: `get_rollen_uebersicht` liefert
 * `rollen_waehlbar`, `ist_system_manager` und die Konten; `setze_rollen` prueft
 * jede Vergabe erneut. Die Oberflaeche blendet nur aus (Warnhinweis), was der
 * Server ohnehin verweigert — die letzte Admin-Rolle ist dort nicht entziehbar.
 */
import { ref, computed, onMounted } from 'vue'
import {
  rollenUebersicht, rollenSetzen, bereicheLesen, rollenErklaerung,
} from '../../composables/useRollenRechte.js'
// UI-R8: die EINE Lesehilfe (Textsorten, Reihenfolge) — kein Rollenwissen hier.
import {
  abschnitte as erklaerungsAbschnitte, erklaerungFuer, fehlendeErklaerung, ladefehlerText,
} from '../../composables/rollenErklaerung.mjs'
import DkButton from '../../components/ui/DkButton.vue'
import DkCard from '../../components/ui/DkCard.vue'
import DkHint from '../../components/ui/DkHint.vue'
import DkField from '../../components/ui/DkField.vue'
import DkDialog from '../../components/ui/DkDialog.vue'
import DkEmpty from '../../components/ui/DkEmpty.vue'
import DkErfolgsmeldung from '../../components/ui/DkErfolgsmeldung.vue'
import DkSkelett from '../../components/ui/DkSkelett.vue'
import RrInfo from '../../components/ui/RrInfo.vue'
import VerantwortlicheKarte from '../../components/VerantwortlicheKarte.vue'
// UI-R10b (R-12i): die Verwaltungsrollen stehen EINMAL (`verwaltungsrollen.mjs`)
// — `Anmeldung.vue` sperrt dieselbe Liste.
import { VERWALTUNGSROLLEN } from '../../verwaltungsrollen.mjs'

const laedt = ref(true)
const geladen = ref(false)
const fehler = ref('')
const erfolg = ref('')
const konten = ref([])
const rollenWaehlbar = ref([])
const istSystemManager = ref(false)
const suche = ref('')

const bereiche = ref([])
const bereich = ref('')

const dialog = ref(null)
const gewaehlteRollen = ref([])
const speichert = ref(false)
const dialogFehler = ref('')

// ── UI-R8: Erklärungen (die EINE Quelle) ───────────────────────────────────
const rohErklaerung = ref(null)
const erklaerungLaedt = ref(true)
const erklaerungFehler = ref('')
const erklaerung = computed(() => erklaerungsAbschnitte(rohErklaerung.value))
const systemrollenQuelle = computed(() => rohErklaerung.value?.systemrollen || null)
const ohneErklaerung = computed(() => fehlendeErklaerung(rollenWaehlbar.value, systemrollenQuelle.value))

/** Erklärung zu einem Rollennamen der Rollenauswahl (null = kein ⓘ). */
function erklaerungVon(name) {
  return erklaerungFuer(systemrollenQuelle.value, name)
}

async function ladeErklaerung() {
  erklaerungLaedt.value = true
  erklaerungFehler.value = ''
  try {
    rohErklaerung.value = await rollenErklaerung()
  } catch (e) {
    // Die Rollen gelten auch ohne Beschreibung; das wird IMMER gesagt (Review
    // R8-7). Den Text baut `ladefehlerText` — dort ist er getestet.
    erklaerungFehler.value = ladefehlerText(e)
    rohErklaerung.value = null
  } finally {
    erklaerungLaedt.value = false
  }
}

// `VERWALTUNGSROLLEN` steht in `verwaltungsrollen.mjs` (eine Quelle).

const gefiltert = computed(() => {
  const begriff = suche.value.trim().toLowerCase()
  if (!begriff) return konten.value
  return konten.value.filter((k) =>
    (k.anzeige || '').toLowerCase().includes(begriff)
    || (k.email || '').toLowerCase().includes(begriff)
    || (k.user || '').toLowerCase().includes(begriff))
})

const gewaehlt = computed(() => {
  const treffer = bereiche.value.find((b) => b.id === bereich.value)
  return treffer ? { typ: treffer.typ, name: treffer.name } : { typ: 'Gruppe', name: '' }
})

const beruehrtVerwaltung = computed(() => {
  if (!dialog.value) return false
  const alt = new Set(dialog.value.rollen || [])
  const neu = new Set(gewaehlteRollen.value)
  return VERWALTUNGSROLLEN.some((r) => alt.has(r) !== neu.has(r))
})

async function laden() {
  laedt.value = true
  fehler.value = ''
  try {
    const daten = await rollenUebersicht()
    konten.value = daten.konten || []
    rollenWaehlbar.value = daten.rollen_waehlbar || []
    istSystemManager.value = !!daten.ist_system_manager
    geladen.value = true
  } catch (e) {
    fehler.value = e?.message || 'Die Übersicht konnte nicht geladen werden.'
  } finally {
    laedt.value = false
  }
}

async function ladeBereiche() {
  try {
    const daten = await bereicheLesen()
    bereiche.value = (daten.nodes || []).filter(
      (n) => n.type === 'dienstbereich' || n.type === 'gruppe' || n.type === 'untergruppe',
    ).map((n) => ({
      id: n.id,
      name: n.raw_name,
      label: `${bereichWort(n.type)}: ${n.name}`,
      typ: n.type === 'dienstbereich' ? 'Dienstbereich'
        : n.type === 'untergruppe' ? 'Untergruppe' : 'Gruppe',
    }))
  } catch {
    bereiche.value = []
  }
}

function bereichWort(typ) {
  if (typ === 'dienstbereich') return 'Bereich'
  if (typ === 'untergruppe') return 'Untergruppe'
  return 'Gruppe'
}

function bearbeiten(k) {
  if (!k.mitglied) return
  dialogFehler.value = ''
  dialog.value = k
  gewaehlteRollen.value = [...(k.rollen || [])].filter((r) => rollenWaehlbar.value.includes(r))
}

function schliesseDialog(offen) {
  if (!offen && !speichert.value) dialog.value = null
}

async function speichern() {
  if (!dialog.value || speichert.value) return
  speichert.value = true
  dialogFehler.value = ''
  try {
    await rollenSetzen(dialog.value.mitglied, gewaehlteRollen.value)
    erfolg.value = `Rollen für ${dialog.value.anzeige} gespeichert.`
    dialog.value = null
    await laden()
  } catch (e) {
    dialogFehler.value = e?.message || 'Die Rollen konnten nicht gespeichert werden.'
  } finally {
    speichert.value = false
  }
}

onMounted(() => { laden(); ladeBereiche(); ladeErklaerung() })
</script>

<style scoped>
.rr-abschnitt { display: grid; gap: var(--sp-4); min-width: 0; }
.rr-abschnitt h2, .rr-abschnitt p { margin: 0; }
.rr-hilfe { color: var(--muted); font-size: var(--fs-sm); }
.rr-liste { list-style: none; padding: 0; margin: var(--sp-3) 0 0; display: grid; gap: var(--sp-1); }
.rr-zeile {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) auto;
  align-items: center;
  gap: var(--sp-3);
  padding: var(--sp-3) 0;
  border-bottom: var(--rahmen-breite) solid var(--line);
}
.rr-person { display: flex; flex-direction: column; min-width: 0; overflow-wrap: anywhere; }
.rr-name { font-weight: 550; }
.rr-unter { color: var(--muted); font-size: var(--fs-sm); overflow-wrap: anywhere; }
.rr-schild { font-size: var(--fs-sm); font-weight: 550; }
.rr-hinweis { color: var(--muted); font-size: var(--fs-sm); font-style: italic; }
.rr-schild--gesperrt { color: var(--warn); }
.rr-schild--raus { color: var(--err); }
.rr-rollen { display: flex; flex-wrap: wrap; gap: var(--sp-1); min-width: 0; }
.rr-chip {
  background: var(--surface-2); border: var(--rahmen-breite) solid var(--line);
  border-radius: var(--radius-sm); padding: var(--sp-1) var(--sp-2); font-size: var(--fs-sm);
}
.rr-rollen-liste { list-style: none; padding: 0; margin: var(--sp-2) 0; display: grid; gap: var(--sp-2); }
/* UI-R8b: Rolle und ⓘ stehen in EINER Zeile — der ⓘ direkt hinter dem Namen
   (der Name wächst NICHT, sonst stünde der ⓘ am rechten Rand). Das Erklärfeld
   ist Geschwister dieser Zeile und bekommt eine eigene volle Zeile darunter. */
.rr-rollen-zeile { display: flex; flex-wrap: wrap; align-items: center; gap: var(--sp-1); min-width: 0; }
/* RrInfo liefert ZWEI Geschwister (ⓘ und Erklärfeld) direkt in diese Zeile —
   darum hängen ihre Platzregeln hier und nicht in RrInfo.vue: der ⓘ nimmt
   keinen Raum, das Feld bekommt die eigene volle Zeile darunter. */
.rr-rollen-zeile > .rr-info-knopf { flex: 0 0 auto; }
.rr-rollen-zeile > .rr-info-panel { flex: 1 0 100%; }
.rr-rolle { display: flex; align-items: center; gap: var(--sp-2); min-width: 0; flex: 0 1 auto; }
.rr-rolle input { margin: 0; flex-shrink: 0; }

/* ── UI-R8: „Was bewirkt welche Rolle?“ ─────────────────────────────────── */
.rr-gruppen { display: flex; flex-direction: column; }
.rr-gruppen > * + * { padding-block-start: var(--sp-4); }
.rr-gruppe-titel {
  font-size: var(--fs-sm); font-weight: var(--fw-fett);
  color: var(--muted); text-transform: uppercase; letter-spacing: 0.04em;
}
.rr-erklaerungen { display: flex; flex-direction: column; }
.rr-erklaerung {
  display: grid; grid-template-columns: minmax(0, 12rem) minmax(0, 1fr);
  align-items: start;
  padding-block: var(--sp-2);
}
.rr-erklaerung > * + * { padding-inline-start: var(--sp-3); border-inline-start: var(--rahmen-breite) solid var(--line); }
.rr-erklaerung-titel { font-weight: var(--fw-fett); }
.rr-erklaerung-text { display: flex; flex-direction: column; min-width: 0; }
.rr-erklaerung-text > * + * { padding-block-start: var(--sp-1); }
.rr-erklaerung-kurz { text-wrap: pretty; }
.rr-rollenname { color: var(--muted); font-size: var(--fs-sm); }
.rr-erklaerung-unter {
  color: var(--muted); font-size: var(--fs-sm); font-weight: var(--fw-fett);
  text-transform: uppercase; letter-spacing: 0.04em;
}
.rr-erklaerung-liste {
  padding-inline-start: var(--sp-4);
  display: flex; flex-direction: column;
  list-style: disc; font-size: var(--fs-sm);
}
.rr-erklaerung-liste--nein { color: var(--muted); }

@media (max-width: 720px) {
  .rr-zeile { grid-template-columns: 1fr; }
  /* Am Handy stehen Rollenname und Erklärung untereinander. */
  .rr-erklaerung { grid-template-columns: 1fr; }
}
</style>
