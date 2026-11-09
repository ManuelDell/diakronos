<template>
  <DkCard title="Auf der Website als Ansprechpartner erscheinen" anker="website-ansprechpartner">
    <div class="we-abschnitt" data-we-abschnitt="einwilligung">
      <DkSkelett v-if="laedt && !daten" kurz form="zeilen" :anzahl="3" text="Dein Stand zur Website wird geladen …" />

      <DkHint v-else-if="fehler" variant="err" role="alert">{{ fehler }}</DkHint>

      <template v-else>
        <!-- ── Der Schalter ───────────────────────────────────────────────
             Erklärt per `aria-describedby` (Kartenvorgabe P1: Schalter mit
             Label, Erklärtext verbunden). Das Kästchen beschreibt sich selbst,
             die Erklärung hängt an SEINER Kennung. -->
        <div class="we-schalter">
          <DkCheckbox
            :model-value="schalterAn"
            :disabled="speichert"
            :aria-describedby="ERKLAERUNG_ID"
            @update:model-value="einwilligungUmschalten"
          >
            Ich bin einverstanden, dass mein Name auf der Website der Gemeinde
            erscheint, wenn ich eine dort gezeigte Aufgabe habe.
          </DkCheckbox>
          <ul :id="ERKLAERUNG_ID" class="we-erklaerung">
            <li v-for="(satz, i) in EINWILLIGUNG_ERKLAERUNG" :key="i">{{ satz }}</li>
          </ul>
        </div>

        <!-- Stand: erteilt / nicht erteilt / erscheint gerade -->
        <div class="we-stand" role="status">
          <DkBadge :variant="stand.einwilligung ? 'ok' : 'neutral'">
            {{ stand.einwilligung ? 'Zustimmung erteilt' : 'Keine Zustimmung' }}
          </DkBadge>
          <span v-if="stand.einwilligung && stand.am" class="we-klein">
            seit {{ formatDatum(stand.am) }}
          </span>
          <span v-if="stand.oeffentlich" class="we-klein">
            Du erscheinst gerade auf der Website.
          </span>
        </div>

        <!-- ── Anzeigename ──────────────────────────────────────────────── -->
        <DkField
          label="Anzeigename (optional)"
          :help="`So soll dein Name auf der Website stehen — zum Beispiel nur der Vorname. Leer heißt: ${vollerName || 'dein voller Name'}.`"
          :error="namenFehler"
          :disabled="!entwurf.einwilligung"
          :maxlength="ANZEIGENAME_MAX"
        >
          <input
            :value="entwurf.anzeigename"
            class="dk-ui-eingabe"
            type="text"
            autocomplete="off"
            :maxlength="ANZEIGENAME_MAX"
            :disabled="!entwurf.einwilligung || speichert"
            :placeholder="vollerName"
            @input="entwurf.anzeigename = $event.target.value"
          />
        </DkField>

        <!-- ── Foto-Zustimmung ──────────────────────────────────────────── -->
        <div class="we-foto">
          <DkCheckbox
            :model-value="entwurf.foto"
            :disabled="!fotoFrei || speichert"
            :aria-describedby="fotoHinweis ? FOTO_HINWEIS_ID : undefined"
            @update:model-value="entwurf.foto = $event"
          >
            Mein Profilfoto darf auf der Website erscheinen.
          </DkCheckbox>
          <p v-if="fotoHinweis" :id="FOTO_HINWEIS_ID" class="we-klein">{{ fotoHinweis }}</p>
        </div>

        <!-- ── Vorschau ─────────────────────────────────────────────────── -->
        <div class="we-vorschau" data-we-vorschau>
          <h3 class="we-vorschau-titel">So erscheinst du</h3>
          <p class="we-vorschau-name">{{ vorschauName || '—' }}</p>
          <p class="we-klein">
            {{ entwurf.einwilligung
              ? 'Name, Funktion und — wenn du es erlaubst — dein Foto. E-Mail, Telefon und Anschrift erscheinen nie.'
              : 'Ohne Zustimmung erscheint nichts von dir auf der Website.' }}
          </p>
          <p v-if="entwurf.einwilligung && entwurf.foto" class="we-klein">
            Das Foto erscheint nur, wenn du zusätzlich der Bild-Nutzung zustimmst.
          </p>
        </div>

        <DkHint v-if="meldung" :variant="meldung.ton" role="alert">
          {{ meldung.text }}
          <DkButton
            v-if="meldung.rueckgaengig"
            size="md"
            variant="secondary"
            :loading="speichert"
            @click="widerrufZuruecknehmen"
          >Rückgängig</DkButton>
        </DkHint>

        <div class="we-aktionen">
          <DkButton
            variant="primary"
            :loading="speichert"
            :disabled="!darfSpeichern"
            :aria-disabled="darfSpeichern ? undefined : 'true'"
            @click="speichernJetzt"
          >Speichern</DkButton>
          <span v-if="!darfSpeichern && !sperrGrund" class="we-klein">
            Es gibt noch nichts zu speichern.
          </span>
          <span v-if="sperrGrund" class="we-klein">{{ sperrGrund }}</span>
        </div>
      </template>
    </div>
  </DkCard>
</template>

<script setup>
/**
 * BS-3b — Profil-Abschnitt „Auf der Website als Ansprechpartner erscheinen“.
 *
 * Zeigt und pflegt AUSSCHLIESSLICH die eigene Einwilligung (BS-3a:
 * `website.meine_einwilligung_lesen|_setzen`). Es gibt keine Stelle, an der
 * eine fremde Einwilligung gesetzt werden könnte — der Server hat keinen
 * Parameter dafür, und dieses Bauteil keine Funktion.
 *
 * Bedienung nach Karte:
 *   • Schalter mit Erklärtext (aria-describedby) — was erscheint, was nie
 *     erscheint, Widerruf wirkt sofort;
 *   • Anzeigename optional (leer = voller Name);
 *   • Foto-Zustimmung NUR wählbar bei Einwilligung UND vorhandenem Foto,
 *     sonst Hinweis;
 *   • Speichern nur bei Änderung (UX3h3, `shared/website-einwilligung.mjs`);
 *   • Widerruf ohne Rückfrage, mit „Rückgängig“ (UX2c-Mechanik) — der
 *     Widerruf ist umkehrbar.
 *
 * `personenFoto`: die Seite kennt das Profilfoto (`profile.foto`); leer =
 * kein Foto vorhanden. Die Einwilligung selbst sagt nichts darüber, ob es
 * eines gibt.
 */
import { computed, onMounted, reactive, ref, useId, watch } from 'vue'
import {
  ANZEIGENAME_MAX,
  EINWILLIGUNG_ERKLAERUNG,
  angezeigterName,
  einwilligungAenderungen,
  fotoHinweis as fotoHinweisAus,
  fotoWaehlbar,
  speichernMoeglich,
  speicherMeldung,
} from '../../../shared/website-einwilligung.mjs'
import { useMeineWebsiteEinwilligung } from '../../composables/useMeineWebsiteEinwilligung.js'
import DkBadge from '../ui/DkBadge.vue'
import DkButton from '../ui/DkButton.vue'
import DkSkelett from '../ui/DkSkelett.vue'
import DkCard from '../ui/DkCard.vue'
import DkCheckbox from '../ui/DkCheckbox.vue'
import DkField from '../ui/DkField.vue'
import DkHint from '../ui/DkHint.vue'

const props = defineProps({
  /** Profilfoto der Person (leer = kein Foto vorhanden). */
  personenFoto: { type: String, default: '' },
  /** Vorname/Nachname für Vorschau und Platzhalter. */
  vorname: { type: String, default: '' },
  nachname: { type: String, default: '' },
})

const kennung = useId()
const ERKLAERUNG_ID = `we-erklaerung-${kennung}`
const FOTO_HINWEIS_ID = `we-foto-hinweis-${kennung}`

const { daten, laedt, fehler, speichert, stand, laden, speichern } = useMeineWebsiteEinwilligung()

/** Was in den Feldern steht (Entwurf). */
const entwurf = reactive({ einwilligung: false, foto: false, anzeigename: '' })
const meldung = ref(null)

const hatFoto = computed(() => Boolean(String(props.personenFoto || '').trim()))
const vollerName = computed(() =>
  [props.vorname, props.nachname].filter(Boolean).join(' ').trim(),
)
const fotoFrei = computed(() => fotoWaehlbar({ einwilligung: entwurf.einwilligung, hatFoto: hatFoto.value }))
const fotoHinweis = computed(() =>
  fotoHinweisAus({
    einwilligung: entwurf.einwilligung,
    hatFoto: hatFoto.value,
    foto: entwurf.foto,
  }),
)
const vorschauName = computed(() =>
  entwurf.einwilligung
    ? angezeigterName(entwurf.anzeigename, { vorname: props.vorname, nachname: props.nachname })
    : '',
)
const prüfung = computed(() => speichernMoeglich(stand.value, entwurf))
const darfSpeichern = computed(() => prüfung.value.speicherbar && !speichert.value)
const sperrGrund = computed(() => prüfung.value.grund)
const namenFehler = computed(() =>
  String(entwurf.anzeigename || '').trim().length > ANZEIGENAME_MAX ? sperrGrund.value : '',
)
/**
 * Der Schalter folgt dem Entwurf — mit EINER Ausnahme: BEIM WIDERRUF steht das
 * Kästchen zuerst noch auf „aus“, auch wenn im Entwurf schon „wieder an“
 * steht. Grund: der Widerruf soll sichtbar geschehen (Kästchen fällt), und
 * „Rückgängig“ hebt ihn dann auf. Ein Kästchen, das nach dem Widerruf sofort
 * wieder „an“ zeigte, wäre für die Person nicht nachvollziehbar.
 */
const schalterAn = computed(() => entwurf.einwilligung && !meldungWiderrufOffen.value)
const meldungWiderrufOffen = computed(
  () => Boolean(meldung.value && meldung.value.rueckgaengig),
)

/** Entwurf auf den geladenen Stand setzen (nach Laden und nach Speichern). */
function entwurfUebernehmen() {
  const s = stand.value
  entwurf.einwilligung = s.einwilligung
  entwurf.foto = s.einwilligung && s.foto
  entwurf.anzeigename = s.anzeigename || ''
}

/**
 * Widerruf: KEINE Rückfrage (Kartenvorgabe) — die Foto-Zustimmung fällt mit
 * und wird nicht mehr angeboten; das lässt sich über „Rückgängig“ zurücknehmen.
 */
function einwilligungUmschalten(an) {
  entwurf.einwilligung = Boolean(an)
  if (!entwurf.einwilligung) entwurf.foto = false
  meldung.value = null
}

async function speichernJetzt() {
  if (!darfSpeichern.value) return
  meldung.value = null
  const ergebnis = await speichern({ ...entwurf })
  if (!ergebnis.ok) {
    if (ergebnis.fehler) meldung.value = { ton: 'err', text: ergebnis.fehler, rueckgaengig: false }
    return
  }
  entwurfUebernehmen()
  meldung.value = speicherMeldung(ergebnis.aenderungen)
}

/** „Rückgängig“ nach einem Widerruf: Zustand von vorher wiederherstellen. */
async function widerrufZuruecknehmen() {
  if (speichert.value) return
  meldung.value = null
  // Der Entwurf steht nach dem Widerruf bereits auf „an“ (Meldung offen);
  // gesendet wird der Unterschied zum GELADENEN Stand — also `einwilligung: true`.
  const ergebnis = await speichern({ ...entwurf, einwilligung: true })
  if (!ergebnis.ok) {
    if (ergebnis.fehler) meldung.value = { ton: 'err', text: ergebnis.fehler, rueckgaengig: false }
    return
  }
  entwurfUebernehmen()
  meldung.value = {
    ton: 'success',
    text: 'Deine Zustimmung gilt wieder.',
    rueckgaengig: false,
  }
}

function formatDatum(wert) {
  const text = String(wert || '')
  if (!text) return ''
  const datum = new Date(text.replace(' ', 'T'))
  if (Number.isNaN(datum.getTime())) return ''
  return datum.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric' })
}

// Der geladene Stand ist der Ausgangspunkt der Felder.
watch(stand, entwurfUebernehmen, { deep: true })

onMounted(async () => {
  await laden()
  entwurfUebernehmen()
})
</script>

<style scoped>
.we-abschnitt { display: grid; grid-template-columns: minmax(0, 1fr); gap: var(--sp-4); min-width: 0; }
.we-schalter { display: grid; grid-template-columns: minmax(0, 1fr); gap: var(--sp-2); min-width: 0; }
.we-erklaerung {
  margin: 0;
  padding-left: var(--sp-5);
  display: grid;
  gap: var(--sp-1);
  color: var(--muted);
  font-size: var(--fs-sm);
}
.we-stand { display: flex; flex-wrap: wrap; align-items: center; gap: var(--sp-2); min-width: 0; }
.we-klein { margin: 0; color: var(--muted); font-size: var(--fs-sm); }
.we-foto { display: grid; grid-template-columns: minmax(0, 1fr); gap: var(--sp-1); min-width: 0; }
.we-vorschau {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: var(--sp-1);
  padding: var(--sp-3);
  border-radius: var(--radius);
  background: var(--surface-2);
  min-width: 0;
}
.we-vorschau-titel {
  margin: 0;
  font-size: var(--fs-xs);
  font-weight: var(--fw-fett);
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.we-vorschau-name { margin: 0; font-size: var(--fs-h4); font-weight: var(--fw-fett); color: var(--text); overflow-wrap: anywhere; }
.we-aktionen { display: flex; flex-wrap: wrap; align-items: center; gap: var(--sp-3); }
</style>
