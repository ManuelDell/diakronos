<template>
  <div class="sk-abschnitt">
    <h2>Datensicherung</h2>
    <p>Die App sichert sich selbst: einmal am Tag die Datenbank und die
      hochgeladenen Dateien. Du stellst hier ein, ob und wann das geschieht und
      wie lange die Sicherungen aufbewahrt werden.</p>

    <DkHint v-if="laedt" role="status">Datensicherung wird geladen …</DkHint>
    <DkHint v-if="fehler" variant="err" role="alert">{{ fehler }}</DkHint>
    <DkHint v-if="erfolg" role="status">{{ erfolg }}</DkHint>
    <DkButton v-if="!geladen && !laedt" variant="secondary" @click="laden">Erneut laden</DkButton>

    <template v-if="geladen">
      <!-- ── Einstellungen ─────────────────────────────────────────────── -->
      <form @submit.prevent="einstellungenSpeichern">
        <fieldset class="sk-felder">
          <DkCard title="Automatisch sichern">
            <label class="sk-schalter">
              <input v-model="automatisch" type="checkbox" />
              <span>Täglich automatisch sichern</span>
            </label>
            <DkField label="Uhrzeit" help="Zu dieser Uhrzeit läuft die Sicherung (Ortszeit)."
              v-slot="feld">
              <input v-bind="feld" v-model="uhrzeit" class="dk-ui-eingabe" type="time"
                step="60" required />
            </DkField>
            <p v-if="naechsterLauf" class="sk-hilfe">
              Der nächste automatische Lauf ist am {{ naechsterLauf }}.
            </p>
            <p v-else class="sk-hilfe">Automatische Sicherungen sind ausgeschaltet.</p>
          </DkCard>

          <DkCard title="Aufbewahrung">
            <DkField label="Sicherungen aufbewahren für" required
              help="Pflichtfeld. Mindestens 1 Tag, höchstens 3650 Tage."
              v-slot="feld">
              <span class="sk-einheit">
                <input v-bind="feld" v-model.number="aufbewahrungTage" class="dk-ui-eingabe"
                  type="number" min="1" max="3650" step="1" inputmode="numeric" required />
                <span>Tage</span>
              </span>
            </DkField>
            <DkHint variant="warn">
              Nach jeder Sicherung werden Sicherungen gelöscht, die älter als diese
              Frist sind. Die neueste Sicherung wird nie gelöscht.
            </DkHint>
            <DkHint variant="info">
              Gelöschte Personen (DSGVO) verschwinden aus den Sicherungen erst nach
              Ablauf dieser Frist. Solange eine ältere Sicherung aufbewahrt wird, steht
              die Person dort noch.
            </DkHint>
          </DkCard>

          <DkButton type="submit" variant="primary" :loading="speichert">Speichern</DkButton>
        </fieldset>
      </form>

      <!-- ── Sicherungen ───────────────────────────────────────────────── -->
      <DkCard title="Vorhandene Sicherungen">
        <div class="sk-kopf">
          <p class="sk-hilfe">
            Sicherungen bleiben auf dem Server: die Dateien enthalten alle
            Personendaten und werden nicht über den Browser ausgegeben. Zurückholen
            einer Sicherung ist ein Vorgang für die Betriebsanleitung — bitte dort
            nachschlagen und nicht hier erwarten.
          </p>
          <DkButton variant="primary" :loading="sichert" @click="jetztSichern">Jetzt sichern</DkButton>
        </div>

        <DkHint v-if="!ablage.benutzbar" variant="err" role="alert">{{ ablage.hinweis }}</DkHint>

        <DkTable :spalten="spalten" :leer="!sicherungen.length"
          leer-titel="Noch keine Sicherung"
          leer-text="Sobald die Sicherung einmal gelaufen ist, erscheint sie hier.">
          <tr v-for="s in sicherungen" :key="s.name">
            <td>{{ zeitpunktText(s.zeitpunkt || s.name) }}</td>
            <td>{{ s.ausloeser === 'manuell' ? 'von Hand' : 'automatisch' }}</td>
            <td>{{ groesseText(s.groesse_bytes) }}</td>
            <td>
              <DkBadge :variant="statusText(s.status).ton">{{ statusText(s.status).wort }}</DkBadge>
              <span v-if="s.meldung && s.status !== 'ok'" class="sk-meldung">{{ s.meldung }}</span>
            </td>
            <td class="sk-aktion">
              <DkButton variant="ghost" size="sm" :disabled="sichert"
                @click="frageLoeschen(s)">Löschen</DkButton>
            </td>
          </tr>
        </DkTable>
      </DkCard>
    </template>
  </div>
</template>

<script setup>
/**
 * BACKUP-1 — Einstellungen-Abschnitt „Datensicherung“ (nur System Manager).
 *
 * Zeigt die Einstellungen (automatisch an/aus, Uhrzeit, Aufbewahrung) und die
 * Liste der vorhandenen Sicherungen; „Jetzt sichern“ löst einen Lauf von Hand
 * aus, „Löschen“ entfernt eine einzelne Sicherung nach Rückfrage.
 *
 * Bewusst NICHT hier: Herunterladen und Wiederherstellen (Karte B3) — die
 * Sicherungen enthalten alle Personendaten, der Weg führt über die
 * Kommandozeile (Betriebsanleitung).
 *
 * Die Rückfrage läuft über `bestaetigen()` (DkBestaetigung im App-Rahmen), nicht
 * über `confirm()`: ein Browser-Dialog lässt sich nicht gestalten und ist am
 * Handy nicht verlässlich.
 */
import { ref, computed, onMounted } from 'vue'
import {
  useSicherung, groesseText, zeitpunktText, statusText,
} from '../../composables/useSicherung.js'
import { bestaetigen } from '../../composables/useBestaetigen.js'
import DkButton from '../../components/ui/DkButton.vue'
import DkCard from '../../components/ui/DkCard.vue'
import DkHint from '../../components/ui/DkHint.vue'
import DkField from '../../components/ui/DkField.vue'
import DkTable from '../../components/ui/DkTable.vue'
import DkBadge from '../../components/ui/DkBadge.vue'

const {
  laedt, speichert, sichert, geladen, fehler, erfolg,
  automatisch, uhrzeit, aufbewahrungTage, sicherungen, ablage,
  laden, einstellungenSpeichern, jetztSichern, loeschen,
} = useSicherung()

const spalten = [
  { key: 'zeitpunkt', label: 'Zeitpunkt' },
  { key: 'ausloeser', label: 'Ausgelöst' },
  { key: 'groesse', label: 'Größe', numeric: true },
  { key: 'status', label: 'Status' },
  { key: 'aktion', label: '', width: '110px' },
]

/** Der nächste geplante Lauf — als Satz, nicht als Zeitrechnung im Handy. */
const naechsterLauf = computed(() => {
  if (!automatisch.value) return ''
  const treffer = String(uhrzeit.value || '').match(/^([01]\d|2[0-3]):([0-5]\d)$/)
  if (!treffer) return ''
  const jetzt = new Date()
  const heute = new Date(jetzt.getFullYear(), jetzt.getMonth(), jetzt.getDate(),
    Number(treffer[1]), Number(treffer[2]), 0, 0)
  const ziel = heute > jetzt ? heute : new Date(heute.getTime() + 24 * 60 * 60 * 1000)
  const tag = ziel.toDateString() === jetzt.toDateString()
    ? 'heute' : `${String(ziel.getDate()).padStart(2, '0')}.${String(ziel.getMonth() + 1).padStart(2, '0')}.`
  return `${tag} um ${treffer[1]}:${treffer[2]} Uhr`
})

async function frageLoeschen(zeile) {
  const wann = zeitpunktText(zeile.zeitpunkt || zeile.name)
  const ja = await bestaetigen({
    titel: 'Sicherung löschen',
    text: `Die Sicherung vom ${wann} wird endgültig gelöscht. Das lässt sich nicht `
      + 'rückgängig machen.',
    aktion: 'Löschen',
    abbrechen: 'Abbrechen',
    gefahr: true,
  })
  if (!ja) return
  await loeschen(zeile.name)
}

onMounted(laden)
</script>

<style scoped>
.sk-abschnitt, .sk-felder { display: grid; gap: var(--sp-4); min-width: 0; }
.sk-abschnitt h2, .sk-abschnitt p { margin: 0; }
.sk-felder { padding: 0; border: 0; margin: 0; }
.sk-hilfe { display: block; color: var(--muted); font-size: var(--fs-sm); }
.sk-schalter { display: flex; align-items: flex-start; gap: var(--sp-2); margin-bottom: var(--sp-3); }
.sk-schalter input { margin-top: var(--sp-1); flex-shrink: 0; }
.sk-einheit { display: flex; align-items: center; gap: var(--sp-2); }
.sk-einheit input { max-width: 8rem; }
.sk-kopf { display: flex; flex-wrap: wrap; gap: var(--sp-3); align-items: flex-start;
  justify-content: space-between; margin-bottom: var(--sp-3); }
.sk-kopf .sk-hilfe { flex: 1 1 18rem; }
.sk-meldung { display: block; color: var(--muted); font-size: var(--fs-sm); margin-top: var(--sp-1); }
.sk-aktion { text-align: right; white-space: nowrap; }
</style>
