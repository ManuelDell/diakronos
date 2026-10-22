<template>
  <!-- UXP-R15: Auf dem Handy liegen die Lied-Spalten ausserhalb des
       Sichtbereichs (390 px). Statt seitlich zu scrollen, wird jeder Termin
       eine Karte: Datum/Anlass oben, die Spalten darunter untereinander. -->
  <div v-if="istMobil" class="pr-tabelle-karten">
    <div v-for="t in termine" :key="t.id" class="pr-tabelle-karte" :class="{ 'pr-tabelle-entfaellt': t.entfaellt }">
      <div class="pr-tabelle-karte-kopf">
        <span class="pr-tabelle-datum">{{ datumText(t.datum) }}</span>
        <span v-if="t.uhrzeit" class="pr-tabelle-uhrzeit">{{ uhrzeitText(t.uhrzeit) }}</span>
        <span v-if="t.entfaellt" class="dk-badge dk-badge-danger">entfallen</span>
      </div>
      <div v-if="t.titel" class="pr-tabelle-karte-titel">{{ t.titel }}</div>
      <div v-if="anlaesse(t).length" class="pr-tabelle-karte-anlaesse">
        <span v-for="a in anlaesse(t)" :key="a" class="dk-badge dk-badge-brand">{{ anlassText(a) }}</span>
      </div>
      <PrMeldungen v-if="meldungenZeigen" :meldungen="terminMeldungen(eintraege, t.id)" kompakt :bezeichnung="zeileBezeichnung(t)" />
      <div v-for="s in spaltenOhneAnlass" :key="s.id" class="pr-tabelle-karte-feld">
        <span class="pr-tabelle-karte-name">{{ s.name }}</span>
        <span
          class="pr-tabelle-karte-wert"
          :class="{ 'pr-tabelle-karte-wert--klickbar': !(!s.feld) }"
          @click="s.feld ? $emit('bearbeiten', t, s.pfad) : null"
        >
          <template v-if="gruppeIst(s.feld)">
            <span v-for="(z, zi) in gruppenZellen(t, s)" :key="zi" class="pr-tabelle-karte-zeile">
              <span class="pr-tabelle-gruppen-name">{{ z.name }}</span>
              <span class="pr-tabelle-gruppen-wert">{{ z.text }}<span v-if="z.fixiert" class="pr-tabelle-pin" title="Von Hand festgelegt">📌</span></span>
            </span>
            <span v-if="!gruppenZellen(t, s).length" class="pr-tabelle-leer">–</span>
          </template>
          <template v-else>
            <span v-for="(inst, ii) in instanzen(t, s)" :key="ii" class="pr-tabelle-karte-zeile pr-tabelle-instanz-text">
              {{ inst.text }}<span v-if="inst.fixiert" class="pr-tabelle-pin" title="Von Hand festgelegt">📌</span>
            </span>
            <span v-if="!instanzen(t, s).length" class="pr-tabelle-leer">–</span>
          </template>
        </span>
      </div>
    </div>
    <div v-if="!termine.length" class="pr-tabelle-leer pr-tabelle-karte-leer">
      Für diesen Zeitraum gibt es noch keine Termine.
    </div>
  </div>

  <div v-else class="pr-tabelle-wrap">
    <table class="pr-tabelle">
      <thead>
        <tr>
          <th class="pr-tabelle-termin">Termin</th>
          <th v-for="s in spalten" :key="s.id">{{ s.name }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="t in termine" :key="t.id" :class="{ 'pr-tabelle-entfaellt': t.entfaellt }">
          <td class="pr-tabelle-termin">
            <span class="pr-tabelle-datum">{{ datumText(t.datum) }}</span>
            <PrMeldungen v-if="meldungenZeigen" :meldungen="terminMeldungen(eintraege, t.id)" kompakt :bezeichnung="zeileBezeichnung(t)" />
            <span v-if="t.uhrzeit" class="pr-tabelle-uhrzeit">{{ uhrzeitText(t.uhrzeit) }}</span>
            <span v-if="t.titel" class="pr-tabelle-titelfeld">{{ t.titel }}</span>
            <span v-if="t.entfaellt" class="dk-badge dk-badge-danger">entfallen</span>
            <!-- UXP-R22: Die Anlässe stehen nur noch in der Anlass-Spalte
                 (vorher zusätzlich hier — jeder Feiertag erschien doppelt). -->
          </td>
          <td
            v-for="s in spalten"
            :key="s.id"
            class="pr-tabelle-zelle"
            :class="{ 'pr-tabelle-zelle--anlass': s.anlass }"
            @click="s.anlass ? null : $emit('bearbeiten', t, s.pfad)"
          >
            <!-- Anlass-Spalte: direkt am Termin, kein Feld -->
            <template v-if="s.anlass">
              <span v-for="a in anlaesse(t)" :key="a" class="dk-badge dk-badge-brand">{{ anlassText(a) }}</span>
              <span v-if="!anlaesse(t).length" class="pr-tabelle-leer">–</span>
            </template>
            <!-- Gruppe: Unterfelder als Zeilen, Pfade kommen vom Server -->
            <template v-else-if="gruppeIst(s.feld)">
              <div v-for="(z, zi) in gruppenZellen(t, s)" :key="zi" class="pr-tabelle-gruppe">
                <span class="pr-tabelle-gruppen-name">{{ z.name }}</span>
                <span class="pr-tabelle-gruppen-wert">
                  {{ z.text }}<span v-if="z.fixiert" class="pr-tabelle-pin" title="Von Hand festgelegt">📌</span>
                </span>
              </div>
              <span v-if="!gruppenZellen(t, s).length" class="pr-tabelle-leer">–</span>
            </template>
            <!-- Einfaches Feld: eine Zeile je Instanz, mit Fixierungs- und Regelhinweis -->
            <template v-else>
              <div v-for="(inst, ii) in instanzen(t, s)" :key="ii" class="pr-tabelle-instanz">
                <span class="pr-tabelle-instanz-text">
                  {{ inst.text }}<span v-if="inst.fixiert" class="pr-tabelle-pin" title="Von Hand festgelegt">📌</span>
                </span>
              </div>
            </template>
          </td>
        </tr>
        <tr v-if="!termine.length">
          <td class="pr-tabelle-leer" :colspan="spalten.length + 1">
            Für diesen Zeitraum gibt es noch keine Termine.
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup>
/**
 * Generische Tabellenansicht (Ansicht art 'tabelle'): Termine als Zeilen,
 * deklarierte Spalten. Zellen tragen die Formatvorlagen der Ansicht, zeigen
 * Fixierungen (📌) und Regelmeldungen; Klick öffnet die Bearbeitung über
 * den Server-Slot-Pfad (keine erfundenen Variantenpfade).
 */
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { datumText, uhrzeitText, reihenFelder, reihePraefix } from '../../composables/usePlanrahmen.js'
import { zellenInhalt } from './zellen.js'
import PrMeldungen from './PrMeldungen.vue'
import { terminMeldungen } from './meldungen.mjs'
import { anlassName, sichtbareAnlaesse } from './anlaesse.mjs'

const props = defineProps({
  plan: { type: Object, default: null },
  termine: { type: Array, default: () => [] },
  eintraege: { type: Array, default: () => [] },
  // versionId → definition (mehrere Termin-Versionen in einem Plan)
  definitionen: { type: [Object, Map], default: () => ({}) },
  ansicht: { type: Object, default: () => ({}) },
  // UXP-R19: Regelmeldungen sind internes Planerwissen — Mitglieder duerfen
  // sie nicht sehen. Anzeige nur, wenn der Planaufruf das Bearbeiten erlaubt.
  meldungenZeigen: { type: Boolean, default: false },
})
defineEmits(['bearbeiten'])

const definitionen = computed(() =>
    props.definitionen instanceof Map ? props.definitionen : new Map(Object.entries(props.definitionen || {})))
const erstdefinition = computed(() => {
    for (const d of definitionen.value.values()) if (d) return d
    return null
})

const alleFelder = computed(() => {
    const result = []
    for (const d of definitionen.value.values()) for (const r of reihenFelder(d)) {
        const präfix = reihePraefix(r.id)
        for (const f of r.felder) result.push({ ...f, pfad: präfix + f.id, reihe: r.id })
    }
    return [...new Map(result.map(f => [f.pfad, f])).values()]
})

function feldFinden(pfad) {
    return alleFelder.value.find((f) => f.pfad === pfad) || null
}

const spalten = computed(() => {
    const deklariert = Array.isArray(props.ansicht?.spalten) ? props.ansicht.spalten : []
    const liste = deklariert.length
        ? deklariert.map((id) => ({ id, pfad: id }))
        : alleFelder.value.map((f) => ({ id: f.pfad, pfad: f.pfad }))
    return liste.map((s) => {
        const feld = feldFinden(s.pfad)
        return {
            ...s,
            anlass: !feld && s.id === 'anlass',
            name: feld?.name || s.pfad.split(':').pop().replace(/^anlass$/, 'Anlass'),
            feld,
            format: props.ansicht?.format?.[s.id] || props.ansicht?.format?.[s.pfad] || '',
        }
    })
})

function gruppeIst(feld) { return feld?.art === 'gruppe' }

/** UXP-R22: ohne Sammelanlass „feiertag“ und ohne Doppelungen. */
function anlaesse(t) { return sichtbareAnlaesse(t.anlaesse) }
/** UXP-R22: Katalognamen statt interner Kennungen (Auflösung in anlaesse.mjs). */
function anlassText(a) { return anlassName(a, erstdefinition.value?.anlaesse) }

/** UXP-R15: Mobil (< 640 px) wird die Tabelle zur Kartenliste. */
const MOBIL_ABFRAGE = '(max-width: 640px)'
const istMobil = ref(typeof window !== 'undefined' && window.matchMedia
    ? window.matchMedia(MOBIL_ABFRAGE).matches : false)
let mobilAbhoerer = null
onMounted(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return
    const mq = window.matchMedia(MOBIL_ABFRAGE)
    istMobil.value = mq.matches
    mobilAbhoerer = (e) => { istMobil.value = e.matches }
    if (mq.addEventListener) mq.addEventListener('change', mobilAbhoerer)
    else if (mq.addListener) mq.addListener(mobilAbhoerer)
})
onUnmounted(() => {
    if (typeof window === 'undefined' || !window.matchMedia || !mobilAbhoerer) return
    const mq = window.matchMedia(MOBIL_ABFRAGE)
    if (mq.removeEventListener) mq.removeEventListener('change', mobilAbhoerer)
    else if (mq.removeListener) mq.removeListener(mobilAbhoerer)
})

/** Mobil: Anlass steht im Kartenkopf, damit er nicht doppelt erscheint. */
const spaltenOhneAnlass = computed(() => spalten.value.filter((s) => !s.anlass))

/** DES-R20: Name der Meldungszeile einer Planzeile (Datum, Uhrzeit, Titel). */
function zeileBezeichnung(t) {
    const teile = [datumText(t.datum)]
    const zeit = uhrzeitText(t)
    if (zeit) teile.push(zeit)
    if (t.titel) teile.push(t.titel)
    return teile.filter(Boolean).join(', ')
}

/** Zellzeilen je Spalte — gemeinsame Logik aus zellen.js. */
function zeilenFuer(t, s) {
    const feld = s.anlass ? null : reihenFelder(definitionen.value.get(t.plantyp_version))
        .flatMap(r => r.felder.map(f => ({ ...f, pfad: reihePraefix(r.id) + f.id })))
        .find(f => f.pfad === s.pfad)
    if (!feld) return []
    return zellenInhalt({ eintraege: props.eintraege, plan: props.plan, termin: t, feld: { ...feld, pfad: s.pfad }, format: s.format })
}
function instanzen(t, s) { return s.anlass || s.feld?.art === 'gruppe' ? [] : zeilenFuer(t, s) }
function gruppenZellen(t, s) { return s.feld?.art === 'gruppe' ? zeilenFuer(t, s) : [] }
</script>

<style scoped>
/* UXP-R15: Kartenliste auf dem Handy — Termin oben, Felder darunter. */
.pr-tabelle-karten { display: flex; flex-direction: column; gap: 12px; }
.pr-tabelle-karte {
  border: 1px solid var(--dk-border); border-radius: 12px; background: var(--dk-surface);
  padding: 12px 14px;
}
.pr-tabelle-karte + .pr-tabelle-karte { margin-top: 0; }
.pr-tabelle-karte-kopf { display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap; }
.pr-tabelle-karte .pr-tabelle-datum { display: inline; }
.pr-tabelle-karte .pr-tabelle-uhrzeit { display: inline; }
.pr-tabelle-karte-titel { font-size: 0.82rem; color: var(--dk-text-muted); margin-top: 2px; }
.pr-tabelle-karte-anlaesse { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 6px; }
.pr-tabelle-karte-feld { display: flex; flex-direction: column; gap: 2px; margin-top: 8px; }
.pr-tabelle-karte-name {
  font-size: 0.68rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em;
  color: var(--dk-text-subtle);
}
.pr-tabelle-karte-wert { display: flex; flex-direction: column; gap: 2px; color: var(--dk-text); }
.pr-tabelle-karte-wert--klickbar { cursor: pointer; }
.pr-tabelle-karte-zeile { display: block; }
.pr-tabelle-karte-leer { padding: 14px; text-align: center; }
.pr-tabelle-wrap { overflow-x: auto; border: 1px solid var(--dk-border); border-radius: 12px; background: var(--dk-surface); }
.pr-tabelle { width: 100%; border-collapse: collapse; font-size: 0.84rem; }
.pr-tabelle th, .pr-tabelle td { padding: 10px 14px; text-align: left; vertical-align: top; }
.pr-tabelle thead th {
  position: sticky; top: 0; z-index: 1;
  background: var(--dk-surface-2); color: var(--dk-text-muted);
  font-size: 0.72rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em;
  border-bottom: 1px solid var(--dk-border); white-space: nowrap;
}
.pr-tabelle tbody tr { border-top: 1px solid var(--dk-divider); }
.pr-tabelle tbody tr:hover { background: var(--dk-surface-hover); }
.pr-tabelle-termin { min-width: 180px; }
.pr-tabelle-datum { display: block; font-weight: 600; color: var(--dk-text); }
.pr-tabelle-uhrzeit { display: block; font-size: 0.74rem; color: var(--dk-text-muted); }
.pr-tabelle-titelfeld { display: block; font-size: 0.76rem; color: var(--dk-text-muted); }
.pr-tabelle-termin .dk-badge { margin-top: 4px; margin-right: 4px; }
.pr-tabelle-zelle { cursor: pointer; min-width: 140px; }
.pr-tabelle-zelle:hover { background: color-mix(in oklch, var(--dk-brand-400) 6%, var(--dk-surface)); }
.pr-tabelle-zelle--anlass { cursor: default; }
.pr-tabelle-zelle--anlass:hover { background: transparent; }
.pr-tabelle-leer { color: var(--dk-text-subtle); }
.pr-tabelle-entfaellt { opacity: 0.55; }
.pr-tabelle-entfaellt .pr-tabelle-datum { text-decoration: line-through; }
.pr-tabelle-instanz + .pr-tabelle-instanz { margin-top: 3px; }
.pr-tabelle-instanz-text { color: var(--dk-text); }
.pr-tabelle-pin { margin-left: 4px; font-size: 0.72rem; }
.pr-tabelle-meldung { margin-left: 4px; font-size: 0.72rem; cursor: help; }
.pr-tabelle-gruppe { display: flex; gap: 6px; align-items: baseline; }
.pr-tabelle-gruppe + .pr-tabelle-gruppe { margin-top: 3px; }
.pr-tabelle-gruppen-name { flex-shrink: 0; font-size: 0.72rem; color: var(--dk-text-subtle); min-width: 70px; }
.pr-tabelle-gruppen-wert { color: var(--dk-text); }
</style>
