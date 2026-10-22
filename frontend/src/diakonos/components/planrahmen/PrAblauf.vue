<template>
  <div class="pr-ablauf" :class="{ 'pr-ablauf--programm': modus === 'programm' }">
    <PrMeldungen v-if="bearbeitbar" :meldungen="terminMeldungen(eintraege, termin?.id)" kompakt :bezeichnung="terminBezeichnung" />
    <!-- Programmheft: Kopf -->
    <template v-if="modus === 'programm' && ansicht?.kopf">
      <div class="pr-programm-kopf">{{ kopfText }}</div>
    </template>

    <section v-for="f in ablaufFelder" :key="f.pfad" class="pr-ablauf-feld">
      <h3 v-if="ablaufFelder.length > 1 || !modus.startsWith('programm')" class="pr-ablauf-titel">
        {{ f.name || f.id }}
      </h3>

      <div v-if="!elemente(f.pfad).length" class="pr-ablauf-leer">
        <template v-if="bearbeitbar">
          Noch keine Elemente — füge unten das erste Element hinzu.
        </template>
        <template v-else>Noch keine Elemente geplant.</template>
      </div>

      <!-- Leseansicht -->
      <ol v-if="!bearbeitbar" class="pr-ablauf-liste">
        <li v-for="e in elemente(f.pfad)" :key="e.id" class="pr-ablauf-element">
          <span v-if="nummeriert(f, e.typ)" class="pr-ablauf-nr" :class="{ 'pr-ablauf-nr--verdeckt': nrVerdeckt(f, e.typ) }">{{ nrFuer(f.pfad, e) }}.</span>
          <span class="pr-ablauf-body">
            <span class="pr-ablauf-typ">{{ typName(f, e.typ) }}</span>
            <span v-for="(z, zi) in inhaltZellen(f, e)" :key="zi" class="pr-ablauf-wert">{{ z }}</span>
          </span>
        </li>
      </ol>

      <!-- Bearbeitung: sortierbare Elementliste -->
      <VueDraggable
        v-else
        v-model="listen[f.pfad]"
        class="pr-ablauf-liste pr-ablauf-liste--editierbar"
        handle=".pr-ablauf-griff" :animation="150"
        @end="(evt) => verschieben(f, evt)"
      >
        <li v-for="(e, ei) in listen[f.pfad]" :key="e.id" class="pr-ablauf-element pr-ablauf-element--edit">
          <span class="pr-ablauf-griff" title="Umsortieren">⠿</span>
          <span v-if="nummeriert(f, e.typ)" class="pr-ablauf-nr" :class="{ 'pr-ablauf-nr--verdeckt': nrVerdeckt(f, e.typ) }">{{ nrFuer(f.pfad, e) }}.</span>
          <span class="pr-ablauf-body">
            <span class="pr-ablauf-typ">{{ typName(f, e.typ) }}</span>
            <span v-for="(z, zi) in inhaltZellen(f, e)" :key="zi" class="pr-ablauf-wert">{{ z }}</span>
          </span>
          <button class="dk-btn dk-btn-ghost dk-btn-sm" title="Element entfernen" @click="loeschen(f, ei)">✕</button>
          <div class="pr-element-felder">
            <div v-for="inner in typDeklaration(f, e.typ)?.inhalt || []" :key="inner.id">
              <button class="dk-btn dk-btn-secondary dk-btn-sm"
                @click="$emit('bearbeiten', termin, `${f.pfad}/${e.id}.${inner.id}`)">
                {{ inner.name || inner.id }}: {{ innerWertText(f, e, inner) }}
                <span v-if="findeEintrag(`${f.pfad}/${e.id}.${inner.id}`)?.fixiert" title="Von Hand festgelegt">📌</span>
              </button>
            </div>
          </div>
        </li>
      </VueDraggable>

      <!-- Element hinzufügen -->
      <div v-if="bearbeitbar" class="pr-ablauf-hinzufuegen">
        <select v-model="neuTyp[f.pfad]" class="pr-ablauf-wahl">
          <option value="" disabled>Elementtyp wählen …</option>
          <option v-for="t in typen(f)" :key="t.typ" :value="t.typ">{{ t.name || t.typ }}</option>
        </select>
        <button
          class="dk-btn dk-btn-secondary dk-btn-sm"
          :disabled="!neuTyp[f.pfad]"
          @click="hinzufuegen(f)"
        >Hinzufügen</button>
      </div>
    </section>

    <div v-if="!ablaufFelder.length" class="pr-ablauf-leer">
      Dieser Termin hat kein Ablauffeld.
    </div>

    <!-- Programmheft: Fuß -->
    <template v-if="modus === 'programm' && ansicht?.fuss">
      <div class="pr-programm-fuss">{{ fussText }}</div>
    </template>
  </div>
</template>

<script setup>
/**
 * Ablauf-Liste (Ansicht art 'ablauf') und Programmheft ('programm'):
 * heterogene Elemente je Termin, in Bearbeitung sortierbar (vue-draggable-plus)
 * mit den Bindungs-Operationen des Servers (hinzufuegen/verschieben/loeschen).
 * Nummerierung wird je Elementtyp berechnet, nie gespeichert.
 */
import { computed, reactive, watch } from 'vue'
import { VueDraggable } from 'vue-draggable-plus'
import {
  reihenFelder, reihePraefix, planKontext, formatVorlage, zellenKontext, anzeigeZu,
} from '../../composables/usePlanrahmen.js'
import { zellenInhalt, feldWertText } from './zellen.js'
import { wertAnzeige } from './auswahlwerte.mjs'
import PrMeldungen from './PrMeldungen.vue'
import { terminMeldungen } from './meldungen.mjs'

const props = defineProps({
  plan: { type: Object, default: null },
  termin: { type: Object, default: null },
  eintraege: { type: Array, default: () => [] },
  definitionen: { type: [Object, Map], default: () => ({}) },
  ansicht: { type: Object, default: () => ({}) },
  bearbeitbar: { type: Boolean, default: false },
  modus: { type: String, default: 'ablauf' }, // 'ablauf' | 'programm'
})
const emit = defineEmits(['operationen', 'geaendert', 'bearbeiten'])

const definitionen = computed(() =>
    props.definitionen instanceof Map ? props.definitionen : new Map(Object.entries(props.definitionen || {})))
const definition = computed(() => definitionen.value.get(props.termin?.plantyp_version) || null)

/** DES-R20: Name der Meldungszeile des geoeffneten Termins. */
function terminBezeichnung() {
  const t = props.termin
  if (!t) return ''
  const d = t.datum || t.tag
  if (!d) return t.titel || ''
  const alsDatum = new Date(String(d).slice(0, 10) + 'T00:00:00')
  const text = Number.isNaN(alsDatum.getTime())
    ? String(d)
    : alsDatum.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric' })
  return t.titel ? text + ', ' + t.titel : text
}

/** Alle Ablauffelder der aktiven Terminversion (inkl. Reihen-Präfix). */
const ablaufFelder = computed(() => {
    const result = []
    for (const r of reihenFelder(definition.value)) {
        const präfix = reihePraefix(r.id)
        const sammle = (felder, basis) => {
            for (const f of felder || []) {
                if (f.art === 'ablauf') result.push({ ...f, pfad: basis + präfix + f.id })
                sammle(f.inhalt, basis)
                for (const zweig of [...(f.varianten || []), ...(f.teile || [])]) {
                    const obj = typeof zweig === 'string' ? { id: zweig } : zweig
                    sammle(obj.inhalt, basis)
                }
            }
        }
        sammle(r.felder, '')
    }
    return result
})

/** Lokale, sortierbare Spiegelung der Server-Elementlisten. */
const listen = reactive({})
const neuTyp = reactive({})

function elemente(pfad) {
    return listen[pfad] || []
}

watch(() => props.termin, (t) => {
    const ablauf = t?.ablauf || {}
    for (const f of ablaufFelder.value) {
        listen[f.pfad] = Array.isArray(ablauf[f.pfad]) ? ablauf[f.pfad].map((e) => ({ ...e })) : []
        neuTyp[f.pfad] = ''
    }
}, { immediate: true, deep: true })

watch(ablaufFelder, (felder) => {
    const ablauf = props.termin?.ablauf || {}
    for (const f of felder) {
        if (!listen[f.pfad]) listen[f.pfad] = Array.isArray(ablauf[f.pfad]) ? ablauf[f.pfad].map((e) => ({ ...e })) : []
        if (neuTyp[f.pfad] === undefined) neuTyp[f.pfad] = ''
    }
})

function typen(f) { return (f.elemente || []).map((e) => (typeof e === 'string' ? { typ: e } : e)) }
function typDeklaration(f, typ) { return typen(f).find((t) => t.typ === typ) || null }
function typName(f, typ) { return typDeklaration(f, typ)?.name || typ }
function nummeriert(f, typ) { return !!typDeklaration(f, typ)?.nummeriert }
/**
 * P3-1d (K3): Blendet die separate Nummernspalte nur aus, wenn die im
 * Programmheft verwendete Formatvorlage des Elementtyps die Nummer selbst
 * setzt (`{nr}`). Fehlt `{nr}` in der Vorlage, waere die Nummer sonst ganz weg.
 */
function nrVerdeckt(f, typ) {
    if (props.modus !== 'programm') return false
    const format = props.ansicht?.format?.[typ]
    return typeof format === 'string' && format.includes('{nr}')
}

/** Laufende Nummer je nummeriertem Elementtyp (nur Berechnung). */
function nrFuer(feldPfad, elem) {
    let nr = 0
    for (const e of listen[feldPfad] || []) {
        if (e.typ !== elem.typ) continue
        nr += 1
        if (e.id === elem.id) return nr
    }
    return nr
}

/** Textzeilen des Elementinhalts (formatiert je Elementtyp-Ansicht). */
function inhaltZellen(f, elem) {
    const dek = typDeklaration(f, elem.typ)
    if (!dek) return []
    const format = props.modus === 'programm' ? props.ansicht?.format?.[elem.typ] : null
    if (format) {
        const ctx = { ...planKontext(props.plan, props.termin), nr: nrFuer(f.pfad, elem) }
        for (const inner of dek.inhalt || []) {
            ctx[inner.id] = kontextWert(inner, findeEintrag(`${f.pfad}/${elem.id}.${inner.id}`)?.wert)
        }
        return [formatVorlage(format, ctx)]
    }
    const zeilen = []
    for (const inner of dek.inhalt || []) {
        const pfad = `${f.pfad}/${elem.id}.${inner.id}`
        const format = props.modus === 'programm' ? (props.ansicht?.format?.[elem.typ] || '') : ''
        if (props.modus === 'programm' && format) {
            const instanz = { index: null, selbst: findeEintrag(pfad), unter: neueMap(inner, f, elem) }
            const ctx = { ...planKontext(props.plan, props.termin), nr: nrFuer(f.pfad, elem) }
            const selbst = instanz.selbst?.wert
            if (inner.art === 'eintrag') ctx.eintrag = anzeigeZu(selbst)
            ctx.wert = kontextWert(inner, selbst)
            for (const [id, wert] of instanz.unter) ctx[id] = wert
            const text = formatVorlage(format, ctx)
            if (text) {
                if (!zeilen.includes(text)) zeilen.push(text)
                continue
            }
        }
        for (const z of zellenInhalt({ eintraege: props.eintraege, plan: props.plan, termin: props.termin, feld: { ...inner, pfad }, format: '' })) {
            if (z.text && z.text !== '–') zeilen.push(`${inner.name || inner.id}: ${z.text}`)
        }
    }
    return zeilen
}

/**
 * Kontextwert eines Ablauf-Unterfelds für Formatvorlagen: Personen/Teams/
 * Eintraege als Anzeigeobjekt, `auswahl` als Anzeigename („Männerchor“)
 * (P3-1c A), alles andere unverändert.
 */
function kontextWert(inner, wert) {
    if (inner?.art === 'auswahl') {
        return Array.isArray(wert) ? wert.map((w) => wertAnzeige(inner, String(w))) : wertAnzeige(inner, String(wert))
    }
    if (['person', 'personen', 'team', 'eintrag'].includes(inner?.art)) {
        return Array.isArray(wert) ? wert.map(anzeigeZu) : anzeigeZu(wert)
    }
    return wert
}

/** Beschriftung eines Unterfeld-Knopfs: Name und Anzeigetext des Werts. */
function innerWertText(f, elem, inner) {
    return feldWertText(inner, findeEintrag(`${f.pfad}/${elem.id}.${inner.id}`)?.wert)
}

function findeEintrag(pfad) {
    return props.eintraege.find((e) => e.termin === props.termin?.id && e.feld_pfad === pfad) || null
}

function neueMap(inner, f, elem) {
    const m = new Map()
    for (const u of inner.inhalt || []) {
        const e = findeEintrag(`${f.pfad}/${elem.id}.${u.id}`)
        if (e && e.wert !== null && e.wert !== undefined) {
            m.set(u.id, ['person', 'personen', 'team', 'eintrag'].includes(u.art) ? anzeigeZu(e.wert) : e.wert)
        }
    }
    return m
}

/** Kopf/Fuß des Programmhefts (Plan-, Termin- und Parameterplatzhalter). */
const kopfText = computed(() => formatVorlage(props.ansicht?.kopf, planKontext(props.plan, props.termin)))
const fussText = computed(() => formatVorlage(props.ansicht?.fuss, planKontext(props.plan, props.termin)))

// ── Operationen gegen den Server ───────────────────────────────────────────

function verschieben(f, evt) {
    const vonPos = evt.oldIndex
    const nachPos = evt.newIndex
    if (vonPos === nachPos) return
    const e = listen[f.pfad][nachPos]
    emit('operationen', [{ aktion: 'verschieben', feld_pfad: f.pfad, element_id: e.id, position: nachPos }])
}

function hinzufuegen(f) {
    const typ = neuTyp[f.pfad]
    if (!typ) return
    const position = listen[f.pfad].length
    emit('operationen', [{ aktion: 'hinzufuegen', feld_pfad: f.pfad, typ, position }])
    neuTyp[f.pfad] = ''
}

function loeschen(f, index) {
    const e = listen[f.pfad][index]
    emit('operationen', [{ aktion: 'loeschen', feld_pfad: f.pfad, element_id: e.id }])
}
</script>

<style scoped>
.pr-ablauf-feld + .pr-ablauf-feld { margin-top: 18px; }
.pr-element-felder { display: flex; flex-wrap: wrap; gap: 6px; width: 100%; }
.pr-ablauf-element--edit { flex-wrap: wrap; }
.pr-ablauf-titel { font-size: 0.8rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; color: var(--dk-text-muted); margin: 0 0 8px; }
.pr-ablauf-liste { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 5px; }
.pr-ablauf-element {
  display: flex; align-items: baseline; gap: 10px;
  padding: 8px 12px; border: 1px solid var(--dk-border); border-radius: 10px;
  background: var(--dk-surface);
}
.pr-ablauf-element--edit { cursor: default; }
.pr-ablauf-griff { cursor: grab; color: var(--dk-text-subtle); flex-shrink: 0; user-select: none; }
.pr-ablauf-nr { flex-shrink: 0; min-width: 22px; font-weight: 700; color: var(--dk-accent-d); }
.pr-ablauf-body { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.pr-ablauf-typ { font-size: 0.72rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; color: var(--dk-text-subtle); }
.pr-ablauf-wert { color: var(--dk-text); font-size: 0.86rem; }
.pr-ablauf-leer { font-size: 0.82rem; color: var(--dk-text-muted); padding: 8px 0; }
.pr-ablauf-hinzufuegen { display: flex; gap: 8px; margin-top: 10px; }
.pr-ablauf-wahl {
  padding: 6px 8px; border-radius: 8px; border: 1px solid var(--dk-border);
  background: var(--dk-surface); color: var(--dk-text); font-size: 0.84rem; font-family: inherit;
}
@media print {
  .pr-ablauf-griff, .pr-ablauf-element--edit > button, .pr-element-felder, .pr-ablauf-hinzufuegen { display: none !important; }
  .pr-ablauf-element { break-inside: avoid; }
}
/* Programmheft */
.pr-ablauf--programm { max-width: 720px; margin: 0 auto; padding: 24px; background: var(--surface); color: var(--text); border: 1px solid var(--line); border-radius: 4px; }
.pr-programm-kopf { font-size: 1.2rem; font-weight: 700; text-align: center; white-space: pre-line; margin-bottom: 18px; }
.pr-programm-fuss { font-size: 0.82rem; text-align: center; white-space: pre-line; margin-top: 18px; color: var(--muted); }
.pr-ablauf--programm .pr-ablauf-titel { display: none; }
.pr-ablauf--programm .pr-ablauf-element { border: none; border-radius: 0; padding: 6px 0; background: transparent; }
.pr-ablauf--programm .pr-ablauf-typ { display: none; }
/* UXP-R24 (e) / P3-1d (K3): im Programmheft traegt die Formatvorlage die
   laufende Nummer meist selbst (`{nr}`), z. B. „1 | Lied | Titel“. Die
   separate Nummernspalte daneben ergaebe „1. 1 | …“. Ausgeblendet wird sie
   daher NUR, wenn die verwendete Formatvorlage dieses Elementtyps `{nr}`
   wirklich enthaelt (`ohneNummer` in PrAblauf.vue) — fehlt `{nr}`, bleibt die
   Nummer sichtbar, statt ganz zu verschwinden. */
.pr-ablauf--programm .pr-ablauf-nr--verdeckt { display: none; }
.pr-ablauf--programm .pr-ablauf-wert { font-size: 1rem; }
</style>
