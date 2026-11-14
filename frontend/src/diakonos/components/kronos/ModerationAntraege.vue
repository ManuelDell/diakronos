<template>
  <!-- UI-R4, Punkt 3: „Freigabe-Anträge“ — Kalender (und andere Inhalte), die
       für eine Gruppe oder für alle Mitglieder der Gemeinde freigegeben werden
       sollen. Die Liste kommt aus `api.rechte.get_offene_sichtbarkeits_antraege`
       und enthält NUR, was der Aufrufer jetzt entscheiden darf (der Server
       filtert über den Rechte-Kern) — die Oberfläche entscheidet nichts selbst.
       Ohne Anträge gibt es diesen Abschnitt gar nicht (kein leerer Kasten). -->
  <section v-if="zeilen.length" class="dk-antraege" data-test="freigabe-antraege">
    <h2 class="dk-antraege-titel">
      Freigabe-Anträge
      <DkBadge variant="warn">{{ zeilen.length }}</DkBadge>
    </h2>
    <p class="dk-antraege-hinweis">
      Diese Inhalte sollen für eine Gruppe oder für alle Mitglieder der Gemeinde
      sichtbar werden. Du entscheidest als Nächste/r.
    </p>
    <ul class="dk-antraege-liste">
      <li v-for="z in zeilen" :key="schluessel(z)" class="dk-antrag-karte">
        <div class="dk-antrag-kopf">
          <strong class="dk-antrag-titel">{{ antragSatz(z) }}</strong>
          <!-- UI-R4b (Punkt 6): Der Name kommt reaktiv aus `stufen_titel` —
               trifft er nach den Anträgen ein, zeichnet die Zeile nach. Bis
               dahin steht hier NICHTS (kein „—“ als Dauerzustand, aber auch
               keine Behauptung): UX2d3a verbietet Ladeprosatexte in
               Vorlagen — die Ladeanzeige ist ein Platzhalter, kein Satz. -->
          <span v-if="z.stufeText !== STUFE_UNBEKANNT" class="dk-antrag-stufe">Stufe: {{ z.stufeText }}</span>
        </div>
        <p v-if="meldungFuer(z)" class="dk-antrag-meldung" role="status">{{ meldungFuer(z) }}</p>
        <div class="dk-antrag-aktionen">
          <DkButton
            variant="primary"
            size="md"
            :disabled="busy !== null"
            :aria-label="'Annehmen: ' + antragSatz(z)"
            @click="entscheiden(z, true)"
          >{{ busy === schluessel(z) ? '…' : 'Annehmen' }}</DkButton>
          <DkButton
            variant="secondary"
            size="md"
            :disabled="busy !== null"
            :aria-label="'Ablehnen: ' + antragSatz(z)"
            @click="ablehnen(z)"
          >Ablehnen</DkButton>
        </div>
      </li>
    </ul>
  </section>
</template>

<script setup>
/**
 * ModerationAntraege — Abschnitt „Freigabe-Anträge“ der Prüfliste (UI-R4).
 *
 * Zwei Serveraufrufe, beide vorhanden (kein neuer Endpunkt):
 *   GET  api.rechte.get_offene_sichtbarkeits_antraege →
 *        { antraege: [{ typ, objekt, gruppe, untergruppe, stufe,
 *                       titel, gruppe_name, untergruppe_name, ziel }] }
 *   POST api.rechte.entscheide_sichtbarkeit(typ, objekt, stufe, annehmen)
 *
 * Fehler (403/417) werden als Klartext an der Zeile gezeigt — der Servertext
 * bleibt erhalten, weil nur er weiß, welche Stufe zuständig ist.
 *
 * Ablehnen fragt NACH: eine Ablehnung auf der Gruppenstufe beendet
 * serverseitig auch den Gemeinde-Antrag. Deshalb der Bestätigungsdialog
 * (`bestaetigen`, derselbe Dialog wie im Papierkorb) — kein `confirm()`.
 */
import { computed, onMounted, ref } from 'vue'
import DkBadge from '../ui/DkBadge.vue'
import DkButton from '../ui/DkButton.vue'
import { apiCall } from '../../composables/useApi.js'
import { showToast } from '../../composables/useToast.js'
import { bestaetigen } from '../../composables/useBestaetigen.js'
import {
  alsStufeText,
  antragSatz,
  antragZeilen,
  naechsteStufeName,
  STUFE_UNBEKANNT,
  verweigerungText,
} from './freigabeStufen.mjs'
// UI-R4b (Punkt 6): Die Stufen-Titel kommen vom Server und können NACH den
// Anträgen eintreffen — `stufenNameReaktiv` macht daraus ein computed, das
// dann neu zeichnet. Und der Lader ist EINER je Seite (Punkt 7b).
import { stufenNameReaktiv, stufenTitelEinmalLaden, titelStand } from './freigabeStufenReaktiv.mjs'

const emit = defineEmits(['entschieden'])

/**
 * UI-R4c (Punkt 2): der Titelstand ZUM ZEITPUNKT des Klicks.
 *
 * Der Toast wird im Klick-Handler gebaut und danach per `showToast` angezeigt.
 * Ein `computed` würde dort den Stand des LETZTEN Zeichnens lesen; kommt die
 * kalte Antwort (`stufen_titel: {}`) erst zwischen Zeichnen und Klick an,
 * stünde im Toast noch „—“ — genau das ist der Befund. Deshalb liest der
 * Weiterleitungs-Satz den Stand beim Klick frisch (`titelStand.value`) und
 * gibt bei fehlendem Namen `null` zurück.
 */
function frischerStufenName(stufe) {
  const titel = titelStand.value || {}
  const name = String(titel[stufe] || '').trim()
  return name || null
}

const antraege = ref([])
const busy = ref(null)
const meldungen = ref({})

/**
 * UI-R4b (Punkt 6): Zeilen als COMPUTED.
 *
 * Vorher war `stufeText` beim Erzeugen der Zeile einmal festgeschrieben: kamen
 * die Anträge vor den Stufen-Titeln, blieb „Stufe: —“ für immer stehen. Jetzt
 * liest jede Zeile den reaktiven Stand (`stufenNameReaktiv`), also zeichnet
 * sie neu, sobald `get_rollen_erklaerung` antwortet.
 */
const zeilen = computed(() => antragZeilen(antraege.value, stufenNameReaktiv))

function schluessel(z) {
  return `${z.typ}|${z.objekt}|${z.stufe}`
}

function meldungFuer(z) {
  return meldungen.value[schluessel(z)] || ''
}

async function laden() {
  try {
    const res = await apiCall('diakronos.api.rechte.get_offene_sichtbarkeits_antraege', {})
    antraege.value = Array.isArray(res?.antraege) ? res.antraege : []
  } catch (e) {
    // Ohne Antwort gibt es nichts zu entscheiden — und nichts zu behaupten.
    antraege.value = []
    if (e?.status && e.status !== 403) {
      showToast('Freigabe-Anträge konnten nicht geladen werden.', 'error')
    }
  }
}

/**
 * UI-R4b (Punkt 5): Toast nach einem Entscheid aus der SERVER-Antwort.
 *
 * Vorher stand fest „Freigegeben … für alle Mitglieder der Gemeinde“, auch
 * wenn auf der Gruppenstufe nur eine Stufe abgehakt war und der Antrag noch
 * bei der Gemeinde-Moderation lag (`gemeinde_status` = „beantragt“).
 *
 * `entscheide_sichtbarkeit` (rechte/verwaltung.py) antwortet mit
 * `{success, gruppe_status, gemeinde_status}` — und NUR damit. Die Antwort
 * dieses Endpunkts kennt keine Stufen-Auskunft (kein „nächste Stufe“, keine
 * Liste offener Stufen); die Oberfläche darf solche Felder nicht erfinden.
 * Ausgewertet wird deshalb genau das, was der Server wirklich sagt:
 *  · Ablehnung → „Abgelehnt …“.
 *  · `meldung` im Text (falls der Server je eine mitschickt) → wörtlich.
 *  · ZIEL erreicht: bei `ziel = 'gemeinde'` steht `gemeinde_status` auf
 *    „aktiv“, bei `ziel = 'gruppe'` `gruppe_status` → wirklich freigegeben.
 *  · Sonst ist nur EINE Stufe abgehakt → „geht jetzt an …“ / „wartet auf …“.
 *  · Ohne jede Statusauskunft (alte Antwort) → neutral „Angenommen …“,
 *    ausdrücklich OHNE „für alle Mitglieder der Gemeinde“ zu behaupten.
 *
 * @param {ReturnType<typeof antragSatz>} satz
 * @param {boolean} annehmen
 * @param {object|null|undefined} antwort
 * @param {'gruppe'|'gemeinde'|null} [ziel] Ziel des Antrags (aus der Zeile).
 * @returns {{text: string, ton: 'success'|'warning'}}
 */
function entscheidMeldung(satz, annehmen, antwort, ziel = null) {
  if (!annehmen) return { text: `Abgelehnt: ${satz}.`, ton: 'warning' }
  const zielErreicht = istZielErreicht(antwort, ziel)
  const serverMeldung = String(antwort?.meldung || '').trim()
  if (serverMeldung) {
    return { text: serverMeldung, ton: zielErreicht === true ? 'success' : 'warning' }
  }
  if (zielErreicht === true) {
    return { text: `Freigegeben: ${satz}.`, ton: 'success' }
  }
  if (zielErreicht === false) {
    // Eine Stufe ist abgehakt, das Ziel noch nicht erreicht: die nächste
    // Stufe beim Namen nennen, sonst neutral „geht weiter“. Der Name ist eine
    // STUFE („die Freigabe der Stufe „Alle Mitglieder der Gemeinde““), keine
    // Adresse — sonst klänge es nach erteilter Freigabe für alle.
    const naechste = alsStufeText(naechsteStufeName(antwort) || zielStufeName(ziel))
    return {
      text: naechste
        ? `Stufe freigegeben — der Antrag geht jetzt an ${naechste}.`
        : 'Stufe freigegeben — der Antrag geht jetzt an die nächste Stufe.',
      ton: 'warning',
    }
  }
  // Keine Auskunft: den Erfolg nicht über den Antrag hinaus behaupten.
  return { text: `Angenommen: ${satz}.`, ton: 'warning' }
}

/** „aktiv“ aus dem Rechte-Kern — der einzige „freigegeben“-Zustand. */
const STATUS_AKTIV = 'aktiv'

/**
 * Hat der Entscheid das ZIEL des Antrags erreicht?
 *
 * Liest ausschließlich die Felder, die `entscheide_sichtbarkeit` wirklich
 * liefert. `true` = Ziel erreicht, `false` = nur eine Stufe weiter,
 * `null` = keine Auskunft (alte Antwort / fremder Server).
 *
 * @param {object|null|undefined} antwort
 * @param {'gruppe'|'gemeinde'|null} ziel
 * @returns {boolean|null}
 */
function istZielErreicht(antwort, ziel) {
  if (!antwort || typeof antwort !== 'object') return null
  if (ziel === 'gemeinde') {
    const status = String(antwort.gemeinde_status || '').trim()
    if (!status) return null
    return status === STATUS_AKTIV
  }
  if (ziel === 'gruppe') {
    const status = String(antwort.gruppe_status || '').trim()
    if (!status) return null
    return status === STATUS_AKTIV
  }
  // Ziel unbekannt (alte Zeile ohne `ziel`): nur dann „fertig“, wenn der
  // Server ausdrücklich BEIDE Stufen als aktiv meldet — sonst nichts behaupten.
  const gruppe = String(antwort.gruppe_status || '').trim()
  const gemeinde = String(antwort.gemeinde_status || '').trim()
  if (!gruppe && !gemeinde) return null
  if (gemeinde) return gemeinde === STATUS_AKTIV
  return gruppe === STATUS_AKTIV
}

/**
 * Ziel-Stufe für den Weiterleitungs-Satz (Server-Titel, ohne Platzhalter).
 *
 * UI-R4c (Punkt 2): Fehlen die Titel noch, liefert `stufenNameReaktiv` den
 * neutralen Platzhalter `STUFE_UNBEKANNT` („—“). Vorher landete der im Toast
 * („… geht jetzt an —.“). Hier gibt es dann `null`; der Aufrufer sagt
 * stattdessen „die nächste Stufe“. Gelesen wird der Stand beim KLICK
 * (`frischerStufenName`), nicht der des letzten Zeichnens.
 */
function zielStufeName(ziel) {
  const stufe = ziel === 'gemeinde' || ziel === 'gruppe' ? ziel : null
  return stufe ? frischerStufenName(stufe) : null
}

/**
 * Ablehnen mit Nachfrage: die Ablehnung auf der Gruppenstufe beendet auch
 * den Antrag für alle Mitglieder der Gemeinde (Servernetz). Das steht im
 * Dialog, damit niemand versehentlich mehr ablehnt, als er entscheiden will.
 */
async function ablehnen(z) {
  const ziel = z.ziel === 'gemeinde'
    ? ' Zugleich entfällt damit der Antrag, den Inhalt für alle Mitglieder der Gemeinde freizugeben.'
    : ''
  const ja = await bestaetigen({
    titel: 'Antrag ablehnen?',
    text: `${antragSatz(z)} wird abgelehnt.${ziel}`,
    aktion: 'Ablehnen',
    abbrechen: 'Zurück',
    gefahr: true,
  })
  if (!ja) return
  await entscheiden(z, false)
}

async function entscheiden(z, annehmen) {
  const k = schluessel(z)
  if (busy.value !== null) return
  busy.value = k
  const rest = { ...meldungen.value }
  delete rest[k]
  meldungen.value = rest
  try {
    // UI-R4b (Punkt 5): Die Antwort auswerten — sie sagt, ob der Antrag
    // weitergeht (Gruppenstufe → Gemeinde-Moderation) oder durch ist.
    const antwort = await apiCall('diakronos.api.rechte.entscheide_sichtbarkeit', {
      typ: z.typ,
      objekt: z.objekt,
      stufe: z.stufe,
      annehmen: annehmen ? 1 : 0,
    })
    const meldung = entscheidMeldung(antragSatz(z), annehmen, antwort, z.ziel)
    showToast(meldung.text, meldung.ton)
    await laden()
    emit('entschieden')
  } catch (e) {
    const text = verweigerungText(e, z.stufe)
    meldungen.value = { ...meldungen.value, [k]: text }
    showToast(text, 'error')
  } finally {
    busy.value = null
  }
}

/**
 * UI-R4b (Punkt 6): Stufen-Titel EINMAL je Seite laden (gemeinsamer Lader),
 * gleichzeitig mit den Anträgen. Vorher lud jedes Bauteil für sich.
 */
onMounted(() => {
  // Ein Fehler des Titel-Laders bleibt folgenlos — die Zeile nennt dann
  // keine Stufe, behauptet aber auch keine.
  stufenTitelEinmalLaden(apiCall)
  laden()
})

defineExpose({ laden })
</script>

<style scoped>
.dk-antraege {
  padding: var(--sp-4);
  border-bottom: var(--rahmen-breite) solid var(--line);
}
.dk-antraege-titel {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  font-size: var(--fs-h3);
  margin: 0 0 var(--sp-2);
}
.dk-antraege-hinweis {
  color: var(--muted);
  font-size: var(--fs-sm);
  margin: 0 0 var(--sp-3);
  max-width: 70ch;
}
.dk-antraege-liste {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
  margin: 0;
  padding: 0;
  list-style: none;
}
.dk-antrag-karte {
  border: var(--rahmen-breite) solid var(--line);
  border-radius: var(--radius);
  padding: var(--sp-3);
  background: var(--surface);
}
.dk-antrag-kopf {
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-2);
  align-items: baseline;
  justify-content: space-between;
}
.dk-antrag-titel {
  font-size: var(--fs);
  color: var(--text);
  /* Lange Kalendernamen brechen um statt die Zeile zu sprengen. */
  overflow-wrap: anywhere;
}
.dk-antrag-stufe {
  font-size: var(--fs-sm);
  color: var(--warn);
  font-weight: var(--fw-mittel);
  white-space: nowrap;
}
.dk-antrag-meldung {
  margin: var(--sp-2) 0 0;
  font-size: var(--fs-sm);
  color: var(--muted);
  overflow-wrap: anywhere;
}
.dk-antrag-aktionen {
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-2);
  margin-top: var(--sp-3);
}
/* K4: bei Fingerbedienung sind die Knöpfe 44 px hoch. */
@media (pointer: coarse) {
  .dk-antrag-aktionen :deep(.dk-ui-btn) { min-height: 44px; }
}
</style>
