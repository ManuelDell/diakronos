<template>
  <div class="sk-abschnitt">
    <h2>Datensicherung</h2>
    <p>Die App sichert sich selbst: einmal am Tag die Datenbank und die
      hochgeladenen Dateien. Du stellst hier ein, ob und wann das geschieht und
      wie lange die Sicherungen aufbewahrt werden.</p>

    <DkSkelett v-if="laedt" form="zeilen" :anzahl="4" text="Datensicherung wird geladen …" />
    <DkHint v-if="fehler" variant="err" role="alert">{{ fehler }}</DkHint>
    <DkErfolgsmeldung :text="erfolg" />
    <DkButton v-if="!geladen && !laedt" variant="secondary" @click="laden">Erneut versuchen</DkButton>

    <template v-if="geladen">
      <!-- ── Einstellungen ─────────────────────────────────────────────── -->
      <form @submit.prevent="speichernMitStand">
        <fieldset class="sk-felder">
          <DkCard title="Automatisch sichern" anker="automatisch">
            <label class="sk-schalter">
              <input v-model="automatisch" type="checkbox" />
              <span>Täglich automatisch sichern</span>
            </label>
            <DkField label="Uhrzeit" anker="uhrzeit" help="Zu dieser Uhrzeit läuft die Sicherung (Ortszeit)."
              v-slot="feld">
              <input v-bind="feld.feldProps" v-model="uhrzeit" class="dk-ui-eingabe" type="time"
                step="60" required />
            </DkField>
            <p v-if="naechsterLauf" class="sk-hilfe">
              Der nächste automatische Lauf ist am {{ naechsterLauf }}.
            </p>
            <p v-else class="sk-hilfe">Automatische Sicherungen sind ausgeschaltet.</p>
          </DkCard>

          <DkCard title="Aufbewahrung">
            <DkField label="Sicherungen aufbewahren für" required anker="aufbewahrungstage"
              help="Pflichtfeld. Mindestens 1 Tag, höchstens 3650 Tage."
              v-slot="feld">
              <span class="sk-einheit">
                <input v-bind="feld.feldProps" v-model.number="aufbewahrungTage" class="dk-ui-eingabe"
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

          <DkButton type="submit" variant="primary" :loading="speichert"
            :disabled="!kannSpeichern" :aria-disabled="kannSpeichern ? undefined : 'true'"
            :title="kannSpeichern ? undefined : 'Keine Änderung zum Speichern'">Speichern</DkButton>
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
              <DkButton variant="ghost" size="md" :disabled="sichert"
                @click="frageLoeschen(s)">Löschen</DkButton>
            </td>
          </tr>
        </DkTable>
      </DkCard>
    </template>

    <!-- UX2c (C1): Sicherung löschen ist endgültig (die Datei ist danach weg,
         ein Zurück gibt es nicht) — der EINE Endgültig-Dialog der App. -->
    <DkEndgueltig
      v-model="loeschenOffen"
      titel="Sicherung endgültig löschen?"
      :text="`Die Sicherung vom ${loeschensZielText} wird gelöscht. Der Stand ist danach dauerhaft weg — das lässt sich nicht rückgängig machen.`"
      aktion="Sicherung endgültig löschen"
      @bestaetigen="loeschenAusfuehren"
    />
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
 * Die Rückfrage läuft über `DkEndgueltig` (UX2c, der EINE Endgültig-Dialog im
 * App-Rahmen), nicht über `confirm()`: ein Browser-Dialog lässt sich nicht
 * gestalten und ist am Handy nicht verlässlich. Löschen ist hier wirklich
 * endgültig (kein Papierkorb für Sicherungsdateien), darum Frage + Folge und
 * der gefährliche Knopf am Ende.
 */
import { ref, computed, onMounted, watch } from 'vue'
import {
  useSicherung, groesseText, zeitpunktText, statusText,
} from '../../composables/useSicherung.js'
// UX3h3: „Speichern nur, wenn geändert“ — EINE Regel für alle Abschnitte.
import { useGeaendertStand } from '../../composables/useGeaendert.js'
// UX2c (C1): der EINE Endgültig-Dialog (Frage, Folge, gefährlicher Knopf).
import DkEndgueltig from '../../components/ui/DkEndgueltig.vue'
import DkButton from '../../components/ui/DkButton.vue'
import DkCard from '../../components/ui/DkCard.vue'
import DkHint from '../../components/ui/DkHint.vue'
import DkField from '../../components/ui/DkField.vue'
import DkTable from '../../components/ui/DkTable.vue'
import DkBadge from '../../components/ui/DkBadge.vue'
import DkErfolgsmeldung from '../../components/ui/DkErfolgsmeldung.vue'
import DkSkelett from '../../components/ui/DkSkelett.vue'

const {
  laedt, speichert, sichert, geladen, fehler, erfolg,
  automatisch, uhrzeit, aufbewahrungTage, sicherungen, ablage,
  laden, einstellungenSpeichern, jetztSichern, loeschen,
} = useSicherung()

// ── UX3h3: „Speichern nur, wenn geändert“ ────────────────────────────────
/**
 * Automatisch an/aus, Uhrzeit und Aufbewahrung. Der Stand wird NACH jedem
 * erfolgreichen Laden UND NACH erfolgreichem Speichern aufgenommen; „Jetzt
 * sichern“ lädt die Liste neu (`laden`); `geladen` bleibt dabei true, der
 * Stand wird also NICHT neu aufgenommen. Unschädlich: `laden` überschreibt
 * die Felder mit den Serverwerten, die dem gemerkten Stand entsprechen.
 */
const stand = useGeaendertStand()
const feldsatz = () => ({
  automatisch: automatisch.value,
  uhrzeit: uhrzeit.value,
  aufbewahrungTage: aufbewahrungTage.value,
})
const geaendert = stand.geaendert(feldsatz)
const kannSpeichern = computed(() => geladen.value && !speichert.value && geaendert.value)
watch(geladen, (ist) => { if (ist) stand.merken(feldsatz) })

/** Absenden wie bisher (`@submit.prevent="einstellungenSpeichern"`). */
async function speichernMitStand() {
  const ok = await einstellungenSpeichern()
  if (ok === false) return false
  stand.merken(feldsatz)
  return true
}

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

/**
 * UX2c (C1): Eine Sicherung zu löschen ist endgültig — es gibt keinen
 * Papierkorb dafür und die Datei ist danach weg. Deshalb der EINE
 * Endgültig-Dialog (Frage, Folge, gefährlicher Knopf), nicht die
 * Ein-Zeilen-Rückfrage.
 */
const loeschenOffen = ref(false)
const loeschenZiel = ref(null)
const loeschensZielText = computed(() => {
  const z = loeschenZiel.value
  if (!z) return ''
  return zeitpunktText(z.zeitpunkt || z.name)
})

function frageLoeschen(zeile) {
  loeschenZiel.value = zeile
  loeschenOffen.value = true
}

async function loeschenAusfuehren() {
  const z = loeschenZiel.value
  if (!z) return
  loeschenOffen.value = false
  await loeschen(z.name)
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
