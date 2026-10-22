<template>
  <PrMeldungen v-if="treffer.length" :meldungen="treffer" :kompakt="kompakt" />
</template>

<script setup>
/**
 * Inline-Prüfmeldungen am betroffenen Eingabepfad — die geteilte Baustelle
 * aller Editor-Abschnisse jenseits des Feldbaums (Termine, Regeln,
 * Deklarationen, Ansichten). `pfad` ist der JSON-Pointer-Basispfad des
 * Eingabefelds relativ zum Definitionsursprung, z. B. 'parameter/0',
 * 'regeln/0/wochen' oder 'ansichten/1/format/dirigent'. Jede Meldung, deren
 * Pfad genau hier liegt oder tiefer darunter, wird über PrMeldungen
 * angezeigt (inkl. Korrekturhinweis mit Mini-Beispiel).
 *
 * `exakt` zeigt nur Meldungen, die GENAU auf dem Pfad liegen (für
 * Kartenebenen, die ihre Unterpfade selbst ausgeben — ohne Dopplung).
 */
import { computed } from 'vue'
import PrMeldungen from './PrMeldungen.vue'
import { meldungenAmFeld } from './editor.mjs'

const props = defineProps({
  meldungen: { type: Array, default: () => [] },
  pfad: { type: String, default: '' },
  kompakt: { type: Boolean, default: true },
  exakt: { type: Boolean, default: false },
})

const treffer = computed(() => {
  if (!props.pfad) return []
  const liste = props.exakt
    ? (props.meldungen || []).filter((m) => normalisiere(m?.pfad) === normalisiere(props.pfad))
    : meldungenAmFeld(props.meldungen, props.pfad)
  return liste.map(anzeigen)
})

function normalisiere(pfad) {
  const ohneSlashes = String(pfad || '').replace(/^\/+|\/+$/g, '')
  return ohneSlashes ? '/' + ohneSlashes : ''
}

/** Hinweis und Beispiel (Mini-Beispiel der Prüfung) gemeinsam anzeigen. */
function anzeigen(m) {
  const beispiel = m?.beispiel ?? m?.detail?.beispiel
  if (beispiel === undefined || beispiel === null || beispiel === '') return m
  const text = typeof beispiel === 'string' ? beispiel : JSON.stringify(beispiel)
  if (m.hinweis && m.hinweis.includes(text)) return m
  return { ...m, hinweis: m.hinweis ? `${m.hinweis} Beispiel: ${text}` : `Beispiel: ${text}` }
}
</script>
