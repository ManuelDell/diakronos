<template>
  <!--
    R6: „Für Gäste freigeben“ — Passwort (zweimal) + Gültigkeit, danach den
    vollständigen Link GENAU EINMAL zeigen. Darunter die vorhandenen
    Gast-Links mit Ablauf/Status und „Widerrufen“ (Rückfrage im Dialog, kein
    window.confirm).

    Der Link steht NUR in der Antwort von `gastlink_erstellen`; gespeichert ist
    serverseitig nur sein Hash. Deshalb wird er hier einmalig angezeigt und
    kann nicht erneut abgerufen werden — das sagt der Hinweis auch.
  -->
  <DkDialog
    :model-value="modelValue"
    size="md"
    :title="`Für Gäste freigeben`"
    :before-close="schliessenMitSchutz"
    @update:model-value="modelValue && $emit('update:modelValue', false)"
  >
    <!-- Schritt 1: neuer Link -->
    <div v-if="!neuerLink" class="r6-gast">
      <p class="r6-gast-einleitung">
        Gäste öffnen „{{ titel }}“ ohne Konto — mit Passwort, und nur bis zum
        Ablauf. Der Link lässt sich jederzeit widerrufen.
      </p>

      <DkField v-slot="feld" label="Passwort für Gäste" required :error="fehler.passwort"
               help="Mindestens 8 Zeichen. Gib es den Gästen getrennt vom Link.">
        <input
          :id="feld.id"
          ref="passwortFeld"
          v-model="form.passwort"
          class="dk-ui-eingabe"
          type="password"
          name="gast-passwort"
          autocomplete="new-password"
          maxlength="200"
          required
          :aria-describedby="feld['aria-describedby']"
          :aria-invalid="feld['aria-invalid']"
        />
      </DkField>

      <DkField v-slot="feld" label="Passwort wiederholen" required :error="fehler.wiederholung">
        <input
          :id="feld.id"
          v-model="form.wiederholung"
          class="dk-ui-eingabe"
          type="password"
          name="gast-passwort-wiederholung"
          autocomplete="new-password"
          maxlength="200"
          required
          :aria-describedby="feld['aria-describedby']"
          :aria-invalid="feld['aria-invalid']"
        />
      </DkField>

      <DkField v-slot="feld" label="Gültig" :error="fehler.tage"
               :help="`Standard ${GAST_TAGE_STANDARD} Tage; ${GAST_TAGE_MIN} bis ${GAST_TAGE_MAX}.`">
        <DkSelect :id="feld.id" :model-value="form.tage" :options="tageOptionen"
                  :aria-describedby="feld['aria-describedby']"
                  @update:model-value="form.tage = $event" />
      </DkField>

      <p v-if="fehler.server" class="r6-gast-fehler" role="alert">{{ fehler.server }}</p>
    </div>

    <!-- Schritt 2: der Link, EINMAL -->
    <div v-else class="r6-gast">
      <p class="r6-gast-hinweis" role="status">
        Der Link ist angelegt und <strong>wird nur jetzt angezeigt</strong>.
        Kopiere ihn jetzt — später lässt er sich nicht erneut anzeigen.
      </p>
      <label class="r6-gast-label" for="r6-gast-link">Link</label>
      <div class="r6-gast-linkzeile">
        <input id="r6-gast-link" ref="linkFeld" class="dk-ui-eingabe" type="text"
               :value="neuerLink.adresse" readonly @focus="$event.target.select()" />
        <DkButton type="button" variant="secondary" @click="kopieren">Kopieren</DkButton>
      </div>
      <p class="r6-gast-klein">
        Gültig bis {{ zeitpunktText(neuerLink.ablauf) }}.
        <span v-if="kopiert" class="r6-gast-kopiert">In die Zwischenablage kopiert.</span>
      </p>
    </div>

    <!-- Vorhandene Links -->
    <div class="r6-gast-liste">
      <h4 class="r6-gast-liste-titel">Bestehende Gast-Links</h4>
      <DkSkelett v-if="listeLaden" form="zeilen" :anzahl="2" text="Gast-Links werden geladen" />
      <p v-else-if="links.length === 0" class="r6-gast-klein">
        Für diesen Inhalt gibt es noch keinen Gast-Link.
      </p>
      <ul v-else class="r6-gast-zeilen">
        <li v-for="l in links" :key="l.id" class="r6-gast-zeile">
          <span class="dk-badge" :class="badgeKlasse(l)">{{ gastlinkStatus(l) }}</span>
          <span class="r6-gast-zeile-text">
            angelegt {{ zeitpunktText(l.erstellt_am) || '—' }} · gültig bis {{ zeitpunktText(l.ablauf) || '—' }}
          </span>
          <DkButton
            v-if="gastlinkAktiv(l)"
            type="button"
            variant="ghost"
            size="sm"
            :disabled="widerrufLaeuft === l.id"
            @click="widerrufen(l)"
          >
            Widerrufen
          </DkButton>
        </li>
      </ul>
      <p v-if="fehler.widerruf" class="r6-gast-fehler" role="alert">{{ fehler.widerruf }}</p>
    </div>

    <template #footer>
      <DkButton type="button" variant="secondary" @click="schliessen">
        {{ neuerLink ? 'Fertig' : 'Schließen' }}
      </DkButton>
      <DkButton
        v-if="!neuerLink"
        type="button"
        variant="primary"
        :loading="erstellenLaeuft"
        :disabled="erstellenLaeuft"
        @click="erstellen"
      >
        Link anlegen
      </DkButton>
    </template>
  </DkDialog>
</template>

<script setup>
/**
 * R6 — Gast-Link-Dialog für einen Beitrag oder Wiki-Artikel.
 *
 * `typ` ist `beitrag` | `wiki`, `objekt` die Kennung des Inhalts. Aufgerufen
 * wird ausschließlich aus Bereichen, in denen der Server `darf_bearbeiten`
 * gemeldet hat — die Endpunkte prüfen es zusätzlich selbst (403).
 */
import { computed, reactive, ref, watch } from 'vue'
import DkDialog from '../ui/DkDialog.vue'
import DkField from '../ui/DkField.vue'
import DkSelect from '../ui/DkSelect.vue'
import DkSkelett from '../ui/DkSkelett.vue'
import DkButton from '../ui/DkButton.vue'
import { bestaetigen } from '../../composables/useBestaetigen.js'
import {
  GAST_TAGE_MAX, GAST_TAGE_MIN, GAST_TAGE_STANDARD,
  gastLinkAdresseFuer, gastlinkAktiv, gastlinkPruefung, gastlinkStatus,
} from '../../composables/r6Gastzugang.mjs'
// UI-R6b: EINE Quelle für Server-Zeitstempel ist `shared/zeit.mjs`; der frühere
// Wrapper `r6Gastzugang.zeitpunktText` war nur eine Umleitung dorthin.
import { serverZeitText as zeitpunktText } from '../../../shared/zeit.mjs'
import { apiCall } from '../../composables/useApi.js'
import { basisPfad } from '../../../shared/basis.js'
import { aktionsfehler } from '../../../shared/fehlertexte.js'

const props = defineProps({
  modelValue: Boolean,
  typ: { type: String, required: true },      // 'beitrag' | 'wiki'
  objekt: { type: String, default: '' },
  titel: { type: String, default: '' },
})

const emit = defineEmits(['update:modelValue'])

const tageOptionen = computed(() => {
  const raus = []
  for (let t = GAST_TAGE_MIN; t <= GAST_TAGE_MAX; t += 1) {
    raus.push({ value: String(t), label: t === 1 ? '1 Tag' : `${t} Tage` })
  }
  return raus
})

const form = reactive({ passwort: '', wiederholung: '', tage: String(GAST_TAGE_STANDARD) })
const fehler = reactive({ passwort: '', wiederholung: '', tage: '', server: '', widerruf: '' })
const erstellenLaeuft = ref(false)
const neuerLink = ref(null)          // { token, adresse, ablauf }
const kopiert = ref(false)
const links = ref([])
const listeLaden = ref(false)
const widerrufLaeuft = ref(null)
const passwortFeld = ref(null)
const linkFeld = ref(null)

function fehlerLeeren() {
  fehler.passwort = ''
  fehler.wiederholung = ''
  fehler.tage = ''
  fehler.server = ''
  fehler.widerruf = ''
}

/** Zurücksetzen beim Öffnen und beim Wechsel des Inhalts. */
watch(() => [props.modelValue, props.objekt], ([offen]) => {
  if (!offen) return
  form.passwort = ''
  form.wiederholung = ''
  form.tage = String(GAST_TAGE_STANDARD)
  neuerLink.value = null
  kopiert.value = false
  fehlerLeeren()
  listeLaden_()
  requestAnimationFrame(() => passwortFeld.value?.focus())
}, { immediate: true })

async function listeLaden_() {
  if (!props.objekt) return
  listeLaden.value = true
  try {
    const antwort = await apiCall('rechte.get_gastlinks', {
      typ: props.typ, objekt: props.objekt,
    })
    links.value = antwort?.links || []
  } catch {
    // Ohne Liste bleibt der Dialog benutzbar; der Server meldet beim Anlegen
    // ohnehin, wenn das Recht fehlt.
    links.value = []
  } finally {
    listeLaden.value = false
  }
}

async function erstellen() {
  if (erstellenLaeuft.value) return
  fehlerLeeren()
  const pruefung = gastlinkPruefung({
    passwort: form.passwort,
    wiederholung: form.wiederholung,
    tage: Number(form.tage),
  })
  if (pruefung) {
    fehler[pruefung.feld] = pruefung.meldung
    return
  }
  erstellenLaeuft.value = true
  try {
    const antwort = await apiCall('rechte.gastlink_erstellen', {
      typ: props.typ,
      objekt: props.objekt,
      passwort: form.passwort,
      tage: Number(form.tage),
    })
    if (!antwort?.token) {
      fehler.server = 'Der Link wurde nicht angelegt. Bitte versuche es erneut.'
      return
    }
    neuerLink.value = {
      token: antwort.token,
      // Vollständige Adresse: derselbe Ursprung wie diese Seite, mit dem
      // Betriebs-Präfix aus dem Boot-Objekt (WEB-5a).
      adresse: gastLinkAdresseFuer(
        { ursprung: window.location.origin, pfad: basisPfad() },
        antwort.token,
      ),
      ablauf: antwort.ablauf,
    }
    form.passwort = ''
    form.wiederholung = ''
    await listeLaden_()
    requestAnimationFrame(() => linkFeld.value?.select())
  } catch (e) {
    // Serverfehler (403/417 = verständliche Meldung des Servers) bleiben stehen.
    fehler.server = aktionsfehler('speichern', e)
  } finally {
    erstellenLaeuft.value = false
  }
}

async function kopieren() {
  const text = neuerLink.value?.adresse || ''
  if (!text) return
  try {
    await navigator.clipboard.writeText(text)
    kopiert.value = true
  } catch {
    // Ohne Zwischenablage (ältere Browser, kein https): Feld markieren —
    // die Person kopiert selbst. Kein Fehlerdialog für eine Kleinigkeit.
    linkFeld.value?.select()
    kopiert.value = false
  }
}

async function widerrufen(link) {
  const ja = await bestaetigen({
    titel: 'Gast-Link widerrufen?',
    text: `Der Link (gültig bis ${zeitpunktText(link.ablauf) || 'unbekannt'}) funktioniert danach sofort nicht mehr. `
      + 'Das lässt sich nicht rückgängig machen.',
    aktion: 'Widerrufen',
    gefahr: true,
  })
  if (!ja) return
  widerrufLaeuft.value = link.id
  fehler.widerruf = ''
  try {
    await apiCall('rechte.gastlink_widerrufen', { link_id: link.id })
    await listeLaden_()
  } catch (e) {
    fehler.widerruf = aktionsfehler('ändern', e)
  } finally {
    widerrufLaeuft.value = null
  }
}

function badgeKlasse(link) {
  const status = gastlinkStatus(link)
  if (status === 'Aktiv') return 'dk-badge-success'
  if (status === 'Widerrufen') return ''
  return 'dk-badge-warning'
}

/**
 * Schließen mit ungespeichertem Passwort: nur nachfragen, solange nichts
 * erstellt wurde. Nach dem Anlegen gibt es nichts zu verlieren (der Link ist
 * ohnehin einmalig).
 */
async function schliessenMitSchutz() {
  if (neuerLink.value || (!form.passwort && !form.wiederholung)) return true
  return bestaetigen({
    titel: 'Freigabe verwerfen?',
    text: 'Das eingegebene Passwort wird nicht gespeichert — es entsteht kein Gast-Link.',
    aktion: 'Verwerfen',
    gefahr: true,
  })
}

function schliessen() {
  emit('update:modelValue', false)
}
</script>

<style scoped>
.r6-gast { display: flex; flex-direction: column; gap: var(--sp-3); }
.r6-gast-einleitung { margin: 0; color: var(--muted); font-size: var(--fs-sm); line-height: 1.5; }

.r6-gast-fehler {
  margin: 0;
  padding: var(--sp-2) var(--sp-3);
  border-radius: var(--radius-sm);
  background: var(--err-soft, var(--surface-2));
  color: var(--err, var(--text));
  font-size: var(--fs-sm);
}

.r6-gast-hinweis {
  margin: 0;
  padding: var(--sp-2) var(--sp-3);
  border-radius: var(--radius-sm);
  background: var(--warn-soft);
  color: var(--warn);
  font-size: var(--fs-sm);
  line-height: 1.5;
}

.r6-gast-label { font-size: var(--fs-sm); font-weight: var(--fw-mittel); color: var(--text); }
.r6-gast-linkzeile { display: flex; gap: var(--sp-2); align-items: center; }
.r6-gast-linkzeile .dk-ui-eingabe { flex: 1 1 auto; min-width: 0; font-family: var(--font-mono); }
.r6-gast-klein { margin: 0; color: var(--muted); font-size: var(--fs-sm); line-height: 1.5; }
.r6-gast-kopiert { color: var(--ok, var(--text)); }

.r6-gast-liste {
  margin-top: var(--sp-4);
  padding-top: var(--sp-3);
  border-top: var(--rahmen-breite) solid var(--divider);
}
.r6-gast-liste-titel {
  margin: 0 0 var(--sp-2);
  font-size: var(--fs-sm);
  font-weight: var(--fw-h);
  color: var(--text);
}
.r6-gast-zeilen { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; }
.r6-gast-zeile {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  padding: var(--sp-2) 0;
  border-bottom: var(--rahmen-breite) solid var(--divider);
  flex-wrap: wrap;
}
.r6-gast-zeile:last-child { border-bottom: none; }
.r6-gast-zeile-text { flex: 1 1 auto; min-width: 0; color: var(--muted); font-size: var(--fs-sm); }

/* Statusfarbe aus den vorhandenen Badge-Varianten (index.css) — kein eigener
   Farbsatz, hell und dunkel gleich. */

/* Der Link und „Kopieren“ stehen am Handy untereinander: reines Stapeln
   innerhalb des Dialogs. Umbruch bei der Mobilgrenze der App
   (`eingabeart.MOBIL_GRENZE_PX` = 720) — der 640px-Wert ist der
   Entscheidungstabelle dieses Pakets vorbehalten. */
@media (max-width: 720px) {
  .r6-gast-linkzeile { flex-direction: column; align-items: stretch; }
}
</style>
