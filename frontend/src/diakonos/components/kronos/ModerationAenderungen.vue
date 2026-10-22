<template>
  <section v-if="eintraege.length" class="dk-aenderungen">
    <h2 class="dk-aenderungen-titel">
      Änderungen an freigegebenen Terminen
      <DkBadge variant="warn">{{ eintraege.length }}</DkBadge>
    </h2>
    <p class="dk-aenderungen-hinweis">
      Diese Termine wurden von Berechtigten geändert. Sie bleiben bis zur
      Freigabe in der bisherigen Fassung sichtbar.
    </p>
    <div
      v-for="e in eintraege"
      :key="e.name"
      class="dk-aenderung-karte"
    >
      <div class="dk-aenderung-kopf">
        <strong>{{ e.neu.element_name || e.alt.element_name }}</strong>
        <span class="dk-aenderung-antragsteller">von {{ e.antragsteller || '–' }}</span>
      </div>
      <table class="dk-aenderung-vergleich">
        <thead>
          <tr><th>Feld</th><th>Bisher</th><th>Neu</th></tr>
        </thead>
        <tbody>
          <tr v-for="z in zeilen(e)" :key="z.feld" :class="{ 'is-abweichend': z.abweichend }">
            <td>{{ z.label }}</td>
            <td>{{ z.alt }}</td>
            <td>{{ z.neu }}</td>
          </tr>
        </tbody>
      </table>
      <p
        v-if="e.geaenderte_felder?.length && !zeilen(e).some(z => z.abweichend)"
        class="dk-aenderungen-hinweis"
      >
        Die Aenderung betrifft nur weitere Ressourcen (z.&nbsp;B. Technik) — sie
        werden beim Freigeben übernommen.
      </p>
      <!-- P1-2-Rest (K1): die Freigabe-Antwort nennt eine Doppelbelegung
           (`belegung_konflikt`). Sie wurde bisher verschluckt — der Moderator
           erfuhr erst beim Speichern im Kalender davon. Hier sichtbar, mit
           Ressource/Zeitraum, und die angebotene Aktion fragt nach. -->
      <div v-if="konfliktFuer(e)" class="dk-aenderung-konflikt">
        <strong>Achtung: Überschneidung</strong>
        <div v-for="(k, i) in konfliktZeilen(e)" :key="i" class="dk-konflikt-zeile">
          {{ k }}
        </div>
        <div class="dk-konflikt-frage">Trotzdem speichern?</div>
        <div class="dk-konflikt-aktionen">
          <DkButton variant="primary" size="sm" :disabled="busy === e.name" @click="trotzdemFreigeben(e)">
            Ja, trotzdem freigeben
          </DkButton>
          <DkButton variant="secondary" size="sm" :disabled="busy === e.name" @click="konfliktVerwerfen(e)">
            Nein, zurück
          </DkButton>
        </div>
      </div>
      <div v-else class="dk-aenderung-aktionen">
        <DkButton variant="primary" size="sm" :disabled="busy === e.name" @click="freigeben(e)">
          Freigeben
        </DkButton>
        <DkButton variant="secondary" size="sm" :disabled="busy === e.name" @click="ablehnen(e)">
          Ablehnen
        </DkButton>
      </div>
    </div>
  </section>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import DkBadge from '../ui/DkBadge.vue'
import DkButton from '../ui/DkButton.vue'
import { apiCall } from '../../composables/useApi.js'
import { showToast } from '../../composables/useToast.js'

const eintraege = ref([])
const busy = ref(null)

const FELDER = [
  { key: 'element_name', label: 'Titel' },
  { key: 'element_start', label: 'Beginn' },
  { key: 'element_end', label: 'Ende' },
  { key: 'ressource', label: 'Ort' },
  { key: 'element_calendar', label: 'Kalender' },
  { key: 'all_day', label: 'Ganztägig' },
]

function formatiere(feld, wert) {
  if (wert === null || wert === undefined || wert === '') return '–'
  if (feld === 'all_day') return wert ? 'Ja' : 'Nein'
  return String(wert)
}

function zeilen(e) {
  return FELDER.map(f => {
    const alt = formatiere(f.key, e.alt?.[f.key])
    const neu = formatiere(f.key, e.neu?.[f.key])
    return { feld: f.key, label: f.label, alt, neu, abweichend: alt !== neu }
  })
}

async function laden() {
  try {
    const res = await apiCall('diakronos.kronos.api.event_crud.get_offene_aenderungen', {})
    eintraege.value = Array.isArray(res) ? res : []
  } catch (err) {
    console.error('Änderungen laden fehlgeschlagen:', err)
  }
}

async function freigeben(e) {
  busy.value = e.name
  try {
    // P1-2-Rest (K1): erst pruefen, dann freigeben. Die Vorabpruefung meldet
    // eine Doppelbelegung, OHNE den Vorschlag anzuwenden — die Freigabe fragt
    // anschliessend nach.
    const pruefung = await apiCall('diakronos.kronos.api.event_crud.aenderung_freigeben', {
      name: e.name, nur_pruefen: 1,
    })
    if (pruefung?.belegung_konflikt?.length) {
      e.belegung_konflikt = pruefung.belegung_konflikt
      e.belegung_konflikt_geprueft = true
      showToast('Überschneidung gefunden — bitte erneut freigeben.', 'warning')
      return
    }
    await freigebenAusfuehren(e)
  } catch (err) {
    showToast(err?.message || 'Änderung konnte nicht übernommen werden.', 'error')
  } finally {
    busy.value = null
  }
}

async function freigebenAusfuehren(e, bestaetigt = false) {
  const res = await apiCall('diakronos.kronos.api.event_crud.aenderung_freigeben', { name: e.name })
  if (res?.belegung_konflikt?.length && !bestaetigt) {
    // Der Server kann zwischen Pruefung und Freigabe neue Ueberschneidungen
    // gefunden haben — dann nicht stillschweigend durchwinken.
    e.belegung_konflikt = res.belegung_konflikt
    e.belegung_konflikt_geprueft = true
    showToast('Überschneidung gefunden — bitte erneut freigeben.', 'warning')
    return
  }
  showToast('Änderung übernommen.', 'success')
  e.belegung_konflikt = []
  e.belegung_konflikt_geprueft = false
  await laden()
}

async function trotzdemFreigeben(e) {
  busy.value = e.name
  try {
    await freigebenAusfuehren(e, true)
  } catch (err) {
    showToast(err?.message || 'Änderung konnte nicht übernommen werden.', 'error')
  } finally {
    busy.value = null
  }
}

function konfliktVerwerfen(e) {
  e.belegung_konflikt = []
  e.belegung_konflikt_geprueft = false
}

function konfliktFuer(e) {
  return (e?.belegung_konflikt || []).length > 0
}

function konfliktZeilen(e) {
  return (e?.belegung_konflikt || []).map(k => {
    const ressource = k?.ressource || k?.ressource_name || 'Ressource'
    const teile = []
    for (const ev of (k?.events || [])) {
      teile.push(`${ev?.element_name || 'Belegt'} (${zeitraumText(ev)})`)
    }
    for (const b of (k?.buchungen || [])) {
      teile.push(`${b?.zweck || b?.titel || 'Buchung'} (${b?.zeitraum || zeitraumText(b)})`)
    }
    return teile.length ? `${ressource}: ${teile.join(', ')}` : `${ressource}: belegt`
  })
}

function zeitraumText(o) {
  if (!o) return ''
  const von = o.element_start || o.datum_von || ''
  const bis = o.element_end || o.datum_bis || ''
  return `${formatiereZeit(von)} – ${formatiereZeit(bis)}`
}

function formatiereZeit(wert) {
  if (!wert) return '–'
  const d = new Date(String(wert).replace(' ', 'T'))
  if (Number.isNaN(d.getTime())) return String(wert)
  return d.toLocaleString('de-DE', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

async function ablehnen(e) {
  busy.value = e.name
  try {
    await apiCall('diakronos.kronos.api.event_crud.aenderung_ablehnen', { name: e.name })
    showToast('Änderung abgelehnt.', 'success')
    await laden()
  } catch (err) {
    showToast(err?.message || 'Änderung konnte nicht abgelehnt werden.', 'error')
  } finally {
    busy.value = null
  }
}

onMounted(laden)
defineExpose({ laden })
</script>

<style scoped>
.dk-aenderungen {
  padding: var(--sp-4);
  border-bottom: 1px solid var(--line);
}
.dk-aenderungen-titel {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  font-size: var(--fs-h3);
  margin: 0 0 var(--sp-2);
}
.dk-aenderungen-hinweis {
  color: var(--muted);
  font-size: var(--fs-sm);
  margin: 0 0 var(--sp-3);
}
.dk-aenderung-karte {
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: var(--sp-3);
  margin-bottom: var(--sp-3);
  background: var(--surface);
}
.dk-aenderung-kopf {
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-2);
  align-items: baseline;
  margin-bottom: var(--sp-2);
}
.dk-aenderung-antragsteller {
  color: var(--muted);
  font-size: var(--fs-sm);
}
.dk-aenderung-vergleich {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--fs-sm);
}
.dk-aenderung-vergleich th,
.dk-aenderung-vergleich td {
  text-align: left;
  padding: 4px 8px;
  border-bottom: 1px solid var(--line);
}
.dk-aenderung-vergleich tr.is-abweichend td {
  color: var(--text);
  font-weight: 600;
}
.dk-aenderung-aktionen {
  display: flex;
  gap: var(--sp-2);
  margin-top: var(--sp-3);
}
/* P1-2-Rest (K1): sichtbare Doppelbelegung vor der Freigabe. */
.dk-aenderung-konflikt {
  margin-top: var(--sp-3);
  padding: var(--sp-3);
  border: 1px solid var(--warn, #b45309);
  border-radius: var(--radius);
  background: var(--warn-bg, rgba(180, 83, 9, 0.08));
  font-size: var(--fs-sm);
}
.dk-konflikt-zeile {
  margin-top: 4px;
  color: var(--text);
}
.dk-konflikt-frage {
  margin-top: var(--sp-2);
  font-weight: 600;
}
.dk-konflikt-aktionen {
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-2);
  margin-top: var(--sp-2);
}
</style>
