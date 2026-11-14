<template>
  <div class="gr-rollen">
    <!-- UI-R1: Die Rollen der Gruppe — HV oben, dann MV, dann GL je
         Untergruppe. Alles, was hier als Knopf erscheint, hängt an den
         Serverfeldern dieser Antwort; durchgesetzt wird ohnehin serverseitig. -->
    <DkSkelett v-if="skelettSichtbar" form="zeilen" :anzahl="3" text="Rollen werden geladen …" />

    <DkEmpty
      v-else-if="fehler"
      icon="!"
      title="Rollen nicht geladen"
      :text="fehler"
      :erneut-versuchen="() => laden()"
    />

    <template v-else>
      <p class="gr-rollen-hinweis">
        <template v-if="istUntergruppe">
          Die Gruppenleitung führt diese Untergruppe. Auswählbar sind nur
          Personen mit einem Zugang (Konto).
        </template>
        <template v-else>
          Wer hier steht, darf diese Gruppe führen: HV/MV die ganze Gruppe,
          GL die jeweilige Untergruppe. Auswählbar sind nur Personen mit einem
          Zugang (Konto).
        </template>
      </p>

      <!-- HV — gehört zur Hauptgruppe, auf einer Untergruppen-Seite nicht. -->
      <section v-if="!istUntergruppe" class="gr-rollen-block" data-rolle="HV">
        <div class="gr-rollen-kopf">
          <h4 class="gr-rollen-titel">Hauptverantwortliche/r</h4>
          <span class="gr-rollen-zahl">{{ geordnet.hv.length }}</span>
        </div>
        <DkEmpty
          v-if="!geordnet.hv.length"
          data-hv-leer
          icon="👤"
          title="Noch keine/r eingetragen"
          text="Den ersten Hauptverantwortlichen setzt der Administrator."
        />
        <ul v-else class="gr-rollen-liste">
          <li v-for="(e, i) in geordnet.hv" :key="'hv-' + schluessel(e, i)" class="gr-rollen-eintrag">
            <span class="gr-rollen-name">{{ e.name }}</span>
            <DkBadge variant="ok">HV</DkBadge>
            <span class="gr-rollen-spacer"></span>
            <span class="gr-rollen-hv-hinweis">nur übertragbar</span>
          </li>
        </ul>

        <p id="gr-rollen-hv-hinweis" class="gr-rollen-erklaerung">{{ HV_HINWEIS }}</p>

        <div v-if="darfHv" class="gr-rollen-aktionen">
          <DkButton variant="secondary" size="md" @click="hvDialogOeffnen">
            HV-Amt übertragen
          </DkButton>
        </div>
      </section>

      <!-- MV — ebenfalls Hauptgruppe. -->
      <section v-if="!istUntergruppe" class="gr-rollen-block" data-rolle="MV">
        <div class="gr-rollen-kopf">
          <h4 class="gr-rollen-titel">Mitverantwortliche/r</h4>
          <span class="gr-rollen-zahl">{{ geordnet.mv.length }}</span>
        </div>
        <DkEmpty
          v-if="!geordnet.mv.length"
          icon="👥"
          title="Noch keine/r eingetragen"
          text="Mitverantwortliche dürfen die Gruppe mitführen und Untergruppen leiten."
        />
        <ul v-else class="gr-rollen-liste">
          <li v-for="(e, i) in geordnet.mv" :key="'mv-' + schluessel(e, i)" class="gr-rollen-eintrag">
            <span class="gr-rollen-name">{{ e.name }}</span>
            <DkBadge variant="neutral">MV</DkBadge>
            <span class="gr-rollen-spacer"></span>
            <!-- Lesende (benutzer = null) bekommen keinen Knopf. -->
            <button
              v-if="darfMv && e.benutzer"
              type="button"
              class="gr-rollen-entfernen"
              :aria-label="`${e.name} als Mitverantwortliche/n entfernen`"
              :disabled="busy === 'mv-' + e.benutzer"
              @click="mvEntfernen(e)"
            >Entfernen</button>
          </li>
        </ul>

        <div v-if="darfMv" class="gr-rollen-aktionen">
          <DkField label="Mitverantwortliche/n hinzufügen">
            <MitgliedAuswahl
              aria-label="Person für Mitverantwortung suchen"
              platzhalter="Name eingeben …"
              :lade-optionen="personenLaden"
              @ausgewaehlt="mvHinzufuegen"
            />
          </DkField>
        </div>
      </section>

      <!-- GL je Untergruppe — auf einer Untergruppen-Seite nur die EIGENE. -->
      <section class="gr-rollen-block" data-rolle="GL">
        <div class="gr-rollen-kopf">
          <h4 class="gr-rollen-titel">{{ istUntergruppe ? 'Gruppenleitung' : 'Gruppenleitung je Untergruppe' }}</h4>
          <span class="gr-rollen-zahl">{{ geordnet.gl.length }}</span>
        </div>

        <p v-if="!untergruppenMitLeitung.length" class="gr-rollen-erklaerung">
          Noch keine Gruppenleitung eingetragen.
        </p>

        <!-- EINE Zeile je Untergruppe: die eingetragenen Leitungen und — wer
             darf — die Auswahl für weitere. Eine Untergruppe KANN mehrere
             Leitungen haben (der Server erlaubt es), darum steht die Auswahl
             auch unter einer bereits besetzten Untergruppe. -->
        <div
          v-for="u in untergruppenMitLeitung"
          :key="'gl-' + u.name"
          class="gr-rollen-untergruppe"
          :data-untergruppe="u.name"
        >
          <p v-if="!istUntergruppe" class="gr-rollen-untertitel">{{ u.anzeige }}</p>
          <ul v-if="u.eintraege.length" class="gr-rollen-liste">
            <li v-for="(e, i) in u.eintraege" :key="'gl-' + schluessel(e, i)" class="gr-rollen-eintrag">
              <span class="gr-rollen-name">{{ e.name }}</span>
              <DkBadge variant="warn">GL</DkBadge>
              <span class="gr-rollen-spacer"></span>
              <button
                v-if="darfGl && e.benutzer"
                type="button"
                class="gr-rollen-entfernen"
                :aria-label="`${e.name} als Gruppenleitung entfernen`"
                :disabled="busy === 'gl-' + e.benutzer"
                @click="glEntfernen(u.name, e)"
              >Entfernen</button>
            </li>
          </ul>
          <!-- UI-R1b: Das Suchfeld braucht eine SICHTBARE Beschriftung, nicht
               nur einen Platzhalter (ein Platzhalter verschwindet beim Tippen
               und ist keine Beschriftung). Der Platzhalter bleibt als Beispiel. -->
          <DkField
            v-if="darfGl"
            :label="istUntergruppe ? 'Gruppenleitung hinzufügen' : `Gruppenleitung für ${u.anzeige} hinzufügen`"
          >
            <!-- GL-BESCHRIFTUNG, UI-R1c: `DkField` setzt
                 `<label for="dk-field-…">`, gibt die Kennung aber nur über den
                 Slot weiter. `MitgliedAuswahl` nimmt sie nicht an — es trägt
                 keine `id` und keinen `v-bind="$attrs"`; das `<label for>` zeigte
                 darum ins Leere und der zugängliche Name des Feldes war nur der
                 Platzhalter. Deshalb traegt das Feld den Text der sichtbaren
                 Beschriftung SELBST als `aria-label` (wie das MV-Feld oben) —
                 Beide Ausdrücke nennen denselben Text; der Test hält sie zusammen. -->
            <MitgliedAuswahl
              :aria-label="istUntergruppe ? 'Gruppenleitung hinzufügen' : `Gruppenleitung für ${u.anzeige} hinzufügen`"
              platzhalter="Name eingeben …"
              :lade-optionen="personenLaden"
              @ausgewaehlt="(p) => glHinzufuegen(u.name, p)"
            />
          </DkField>
        </div>

        <div v-if="darfGl && !untergruppen.length && !istUntergruppe" class="gr-rollen-aktionen">
          <DkHint variant="info">
            Diese Gruppe hat noch keine Untergruppen — eine Gruppenleitung
            ist erst danach möglich.
          </DkHint>
        </div>
      </section>
    </template>

    <!-- ── HV-Amt übertragen: Sicherheitsabfrage ─────────────────────── -->
    <DkDialog v-model="hvDialog" title="HV-Amt übertragen" size="md">
      <div class="gr-hv">
        <p class="gr-hv-text">
          <template v-if="geordnet.hv.length">
            Das Amt geht von {{ geordnet.hv.map(e => e.name).join(', ') }} an die
            neue Person über.
          </template>
          <template v-else>
            Diese Gruppe hat noch keine/n Hauptverantwortliche/n — du setzt die
            erste Person ein.
          </template>
        </p>
        <p class="gr-hv-erklaerung" data-hv-erklaerung>{{ HV_HINWEIS }}</p>

        <DkField label="Neue/r Hauptverantwortliche/r">
          <div class="gr-hv-auswahl" data-hv-auswahl>
            <p v-if="hvPerson" class="gr-hv-gewaehlt">
              Gewählt: <strong>{{ hvPerson.name }}</strong>
              <!-- UI-R1b: „ändern“ ist keine Gefahr — neutrale Klasse statt der
                   roten `gr-rollen-entfernen`. -->
              <button type="button" class="gr-rollen-aendern" @click="hvPerson = null">ändern</button>
            </p>
            <MitgliedAuswahl
              v-else
              aria-label="Neue/n Hauptverantwortliche/n suchen"
              platzhalter="Name eingeben …"
              :lade-optionen="personenLaden"
              @ausgewaehlt="hvPersonWaehlen"
            />
          </div>
        </DkField>

        <DkField :label="`Zur Bestätigung den Namen eintippen${hvPerson ? ': ' + hvPerson.name : ''}`">
          <input
            v-model="hvBestaetigung"
            class="dk-ui-eingabe"
            type="text"
            autocomplete="off"
            data-hv-bestaetigung
            :placeholder="hvPerson ? hvPerson.name : 'zuerst die Person wählen'"
            :disabled="!hvPerson"
            :aria-describedby="'gr-hv-pruefung'"
          />
        </DkField>
        <p id="gr-hv-pruefung" class="gr-hv-pruefung" data-hv-pruefung role="status">
          {{ hvPruefungText }}
        </p>

        <DkCheckbox v-model="alterHvWirdMv" label="Bisherige/r HV wird Mitverantwortliche/r" />
      </div>

      <template #footer>
        <DkButton variant="secondary" @click="hvDialog = false">Abbrechen</DkButton>
        <DkButton
          variant="primary"
          :disabled="!hvBereit || busy === 'hv'"
          :loading="busy === 'hv'"
          @click="hvUebertragenJetzt"
        >HV-Amt übertragen</DkButton>
      </template>
    </DkDialog>
  </div>
</template>

<script setup>
/**
 * RollenEinstellungen — HV, MV und GL einer Gruppe (UI-R1, Teil 1 der
 * Gruppen-Einstellungen).
 *
 * Alle Daten und Rechte kommen vom Server (`diakronos_app.api.rechte.*`):
 *   get_gruppenrollen(gruppe)  → { rollen, darf_hv_mv_ernennen, darf_verwalten }
 *   ernenne_mv / entferne_mv   (nur HV)
 *   ernenne_gl / entferne_gl   (HV/MV, je Untergruppe)
 *   uebertrage_hv              (Sicherheitsabfrage, bestaetigt=true)
 *   get_personen_auswahl       (nur Namen)
 *
 * Diese Komponente entscheidet NICHTS über Rechte; sie blendet aus, was der
 * Server ohnehin verweigert, und zeigt Serverfehler (403/417) als Satz.
 *
 * Untergruppen: `ernenne_gl` erwartet die Untergruppen-KENNUNG (`name`), die
 * Liste der Untergruppen liefert die Detailseite (`get_gruppe_detail`).
 */
import { ref, computed, watch, onMounted } from 'vue'
import DkButton from '../ui/DkButton.vue'
import DkBadge from '../ui/DkBadge.vue'
import DkField from '../ui/DkField.vue'
import DkCheckbox from '../ui/DkCheckbox.vue'
import DkDialog from '../ui/DkDialog.vue'
import DkEmpty from '../ui/DkEmpty.vue'
import DkHint from '../ui/DkHint.vue'
import DkSkelett from '../ui/DkSkelett.vue'
import MitgliedAuswahl from '../MitgliedAuswahl.vue'
import { apiCall } from '../../composables/useApi.js'
import { useLadeSkelett } from '../../composables/useLadeSkelett.js'
import { showToast } from '../../composables/useToast.js'
import { aktionsfehler, fehlertext } from '../../../shared/fehlertexte.js'
import {
  HV_HINWEIS,
  darfGlPflegen,
  darfHvUebertragen,
  darfMvPflegen,
  hvUebertragenPruefen,
  personenAuswahl,
  rollenOrdnen,
} from './gruppenEinstellungen.mjs'

const RECHTS = 'diakronos_app.api.rechte'

const props = defineProps({
  /** Kennung der HAUPTgruppe (auf einer Untergruppen-Seite: der Obergruppe). */
  gruppe: { type: String, required: true },
  /**
   * Kennung der Untergruppe, wenn diese Seite eine Untergruppe zeigt. Dann
   * gibt es AUSSCHLIESSLICH die Gruppenleitung dieser Untergruppe — HV/MV
   * gehören zur Obergruppe und haben hier nichts zu suchen.
   */
  untergruppe: { type: String, default: '' },
  /** Untergruppen der Gruppe: [{ name, anzeigename }]. */
  untergruppen: { type: Array, default: () => [] },
})

const emit = defineEmits(['geaendert'])

/** Ist diese Seite die Seite einer Untergruppe? */
const istUntergruppe = computed(() => Boolean(props.untergruppe))

const laedt = ref(true)
const { skelettSichtbar } = useLadeSkelett(laedt)
const fehler = ref('')
const daten = ref({ rollen: [], darf_hv_mv_ernennen: false, darf_verwalten: false })
/** Laufende Aktion (sperrt genau den einen Knopf, keine Doppelklicks). */
const busy = ref('')

/**
 * R-12c: Name und Untergruppenname kommen vom Server (`name`,
 * `untergruppe_name`) — kein Nachschlagen über die Personensuche mehr.
 * Auf einer Untergruppen-Seite bleibt nur die GL DIESER Untergruppe übrig.
 */
const geordnet = computed(() => rollenOrdnen(daten.value.rollen,
  istUntergruppe.value ? { nurUntergruppe: props.untergruppe } : {}))
const darfMv = computed(() => !istUntergruppe.value && darfMvPflegen(daten.value))
const darfGl = computed(() => darfGlPflegen(daten.value))
const darfHv = computed(() => !istUntergruppe.value && darfHvUebertragen(daten.value))

/** Untergruppen in Anzeigeform — Kennung bleibt für den Server. */
const untergruppen = computed(() => (Array.isArray(props.untergruppen) ? props.untergruppen : [])
  .filter((u) => u && u.name)
  .map((u) => ({ name: String(u.name), anzeige: u.anzeigename || u.untergruppenname || String(u.name) })))

function untergruppeName(kennung) {
  const treffer = untergruppen.value.find((u) => u.name === kennung)
  if (treffer) return treffer.anzeige
  // UI-R1b: Auf der UNTERGRUPPEN-Seite ist `props.untergruppen` leer (die
  // Liste gehört zur Obergruppe) — dort kommt der Name aus der Rollenantwort
  // (`untergruppe_name`, R-12c), NICHT die Kennung.
  const ausRollen = (Array.isArray(daten.value.rollen) ? daten.value.rollen : [])
    .find((r) => String(r?.untergruppe || '') === String(kennung) && r?.untergruppe_name)
  return ausRollen?.untergruppe_name || kennung
}

/** UI-R1b: stabiler `:key` je Zeile — Konto, sonst Rolle + Position. */
function schluessel(eintrag, index) {
  return eintrag?.benutzer || `${eintrag?.rolle || 'x'}-${index}`
}

/**
 * Eine Zeile je Untergruppe, die eine Leitung hat ODER (für wer darf) eine
 * Auswahl anbietet. Leitungen ohne bekannte Untergruppe (sollte der Server je
 * welche liefern) hängen als eigene Zeile mit ihrer Kennung an.
 *
 * Auf einer UNTERGRUPPEN-Seite gibt es genau eine Zeile: die eigene
 * Untergruppe (ihre Kennung ist `props.untergruppe`).
 */
const untergruppenMitLeitung = computed(() => {
  if (istUntergruppe.value) {
    const eigen = untergruppen.value.find((u) => u.name === props.untergruppe)
    return [{
      name: props.untergruppe,
      anzeige: eigen?.anzeige || props.untergruppe,
      eintraege: geordnet.value.gl,
    }]
  }
  const zeilen = untergruppen.value.map((u) => ({
    name: u.name,
    anzeige: u.anzeige,
    eintraege: geordnet.value.gl.filter((e) => e.untergruppe === u.name),
  }))
  const bekannt = new Set(zeilen.map((z) => z.name))
  for (const g of geordnet.value.glJeUntergruppe) {
    if (!g.untergruppe || bekannt.has(g.untergruppe)) continue
    zeilen.push({ name: g.untergruppe, anzeige: g.anzeige, eintraege: g.eintraege })
  }
  if (!darfGl.value) return zeilen.filter((z) => z.eintraege.length)
  return zeilen
})

/**
 * Personen für die Auswahl — über `get_personen_auswahl` (DER Endpunkt der
 * Karte): er liefert Kontokennung (`benutzer`) + Name, also genau das, was
 * `ernenne_mv`/`ernenne_gl`/`uebertrage_hv` erwarten.
 *
 * NICHT `get_gruppe_mitglieder_auswahl`: die liefert bewusst nur `mitglied`
 * (Mitglieds-Kennung) und `name` — die Mitglieds-Kennung ist KEIN Konto, und
 * der Server weist sie als `benutzer` ab (`_pruefe_konto`). Die Namen der
 * BEREITS eingetragenen Personen kommen dagegen aus `get_gruppenrollen`.
 */
async function personenLaden(suche = '') {
  try {
    const res = await apiCall(`${RECHTS}.get_personen_auswahl`, { suche: suche || '', limit: 50 })
    return personenAuswahl(res?.personen)
  } catch (e) {
    throw new Error(fehlertext(e, { text: 'Die Personensuche ist gerade nicht erreichbar.' }))
  }
}

/**
 * Lädt die Rollen der Gruppe.
 *
 * UI-R1b: `still` ist der Weg nach einer Aktion. Dann bleibt die Liste mit
 * ihrem Skelett-/Fehlerzustand stehen (kein Zusammenfallen der Seite); nur der
 * ERSTE Aufbau zeigt das Ladeskelett.
 */
async function laden({ still = false } = {}) {
  if (!props.gruppe) { laedt.value = false; return }
  if (!still) {
    laedt.value = true
    fehler.value = ''
  }
  try {
    const antwort = await apiCall(`${RECHTS}.get_gruppenrollen`, { gruppe: props.gruppe })
    daten.value = {
      rollen: Array.isArray(antwort?.rollen) ? antwort.rollen : [],
      darf_hv_mv_ernennen: Boolean(antwort?.darf_hv_mv_ernennen),
      darf_verwalten: Boolean(antwort?.darf_verwalten),
    }
    // Eine geglückte stille Antwort räumt einen alten Fehler weg.
    fehler.value = ''
  } catch (e) {
    fehler.value = fehlertext(e, { text: 'Die Rollen konnten nicht geladen werden.' })
  } finally {
    laedt.value = false
  }
}

/**
 * EINE Rollen-Aktion: senden und EINMAL nachladen.
 *
 * UI-R1b: Vorher lud jeder Aufruf HIER (`laden()`) UND meldete `geaendert`,
 * worauf die Gruppenseite ihren `fetchGruppe` anwarf und die Karte über
 * `:key` neu gebaut wurde — je Aktion also zweimal `get_gruppenrollen`, dazu
 * `get_personen_auswahl` (verworfen) und `get_gruppe_detail`. Jetzt: stilles
 * Nachladen der Rollen, dann EIN `geaendert` (still auch auf der Seite), und
 * die Personensuche erst, wenn sie wirklich gebraucht wird.
 */
async function ruf(fn, params, schluessel) {
  busy.value = schluessel
  try {
    const antwort = await apiCall(`${RECHTS}.${fn}`, params)
    if (antwort?.success) {
      // Erst wenn der Server bestätigt hat: nachladen und melden. Ein Fehler
      // lässt die bisherige Liste samt Meldung stehen.
      await laden({ still: true })
      emit('geaendert')
    }
    return antwort
  } catch (e) {
    showToast(aktionsfehler('speichern', e), 'error')
    return null
  } finally {
    busy.value = ''
  }
}

// ── MV ────────────────────────────────────────────────────────────────────
async function mvHinzufuegen(person) {
  if (!person?.benutzer) return
  const res = await ruf('ernenne_mv', { gruppe: props.gruppe, benutzer: person.benutzer }, 'mv-neu')
  if (res?.success) showToast(res.bestand ? 'Diese Person war bereits Mitverantwortliche/r.' : `${person.name} ist jetzt Mitverantwortliche/r.`, 'success')
}

async function mvEntfernen(eintrag) {
  const res = await ruf('entferne_mv', { gruppe: props.gruppe, benutzer: eintrag.benutzer }, 'mv-' + eintrag.benutzer)
  if (res?.success) showToast(`${eintrag.name} ist nicht mehr Mitverantwortliche/r.`, 'success')
}

// ── GL ────────────────────────────────────────────────────────────────────
async function glHinzufuegen(untergruppe, person) {
  if (!person?.benutzer) return
  const res = await ruf('ernenne_gl', { untergruppe, benutzer: person.benutzer }, 'gl-neu-' + untergruppe)
  if (res?.success) showToast(res.bestand ? 'Diese Person war bereits Gruppenleitung.' : `${person.name} leitet jetzt ${untergruppeName(untergruppe)}.`, 'success')
}

async function glEntfernen(untergruppe, eintrag) {
  const res = await ruf('entferne_gl', { untergruppe, benutzer: eintrag.benutzer }, 'gl-' + eintrag.benutzer)
  if (res?.success) showToast(`${eintrag.name} ist nicht mehr Gruppenleitung.`, 'success')
}

// ── HV übertragen (Sicherheitsabfrage) ────────────────────────────────────
const hvDialog = ref(false)
const hvPerson = ref(null)
const hvBestaetigung = ref('')
const alterHvWirdMv = ref(true)

const hvPruefung = computed(() => hvUebertragenPruefen({
  neuerHv: hvPerson.value?.benutzer || '',
  name: hvPerson.value?.name || '',
  eingabe: hvBestaetigung.value,
}))
const hvBereit = computed(() => hvPruefung.value.ok)

const hvPruefungText = computed(() => {
  if (!hvPerson.value) return 'Wähle zuerst die neue Person.'
  if (hvPruefung.value.ok) return 'Name stimmt — die Übertragung ist freigegeben.'
  return 'Der eingetippte Name stimmt noch nicht mit der gewählten Person überein.'
})

function hvDialogOeffnen() {
  hvPerson.value = null
  hvBestaetigung.value = ''
  alterHvWirdMv.value = true
  hvDialog.value = true
}

function hvPersonWaehlen(person) {
  hvPerson.value = person?.benutzer ? { benutzer: person.benutzer, name: person.name } : null
}

async function hvUebertragenJetzt() {
  if (!hvBereit.value || !hvPerson.value) return
  busy.value = 'hv'
  try {
    const antwort = await apiCall(`${RECHTS}.uebertrage_hv`, {
      gruppe: props.gruppe,
      neuer_hv: hvPerson.value.benutzer,
      bestaetigt: true,
      alter_hv_wird_mv: alterHvWirdMv.value,
    })
    if (antwort?.success) {
      showToast(`${hvPerson.value.name} ist jetzt Hauptverantwortliche/r.`, 'success')
      hvDialog.value = false
      await laden({ still: true })
      emit('geaendert')
    } else {
      showToast('Die Übertragung wurde nicht bestätigt.', 'error')
    }
  } catch (e) {
    showToast(aktionsfehler('speichern', e), 'error')
  } finally {
    busy.value = ''
  }
}

onMounted(() => laden())
watch(() => [props.gruppe, props.untergruppe], () => laden())
// Neue Untergruppen erscheinen ohne eigenes Zutun: `untergruppenMitLeitung`
// liest `props.untergruppen` direkt, ein eigener Beobachter ist nicht nötig.
</script>

<style scoped>
.gr-rollen { display: flex; flex-direction: column; gap: var(--sp-4); }
.gr-rollen-hinweis { margin: 0; color: var(--muted); font-size: var(--fs-sm); }
.gr-rollen-block { display: flex; flex-direction: column; gap: var(--sp-3); }
.gr-rollen-kopf { display: flex; align-items: baseline; gap: var(--sp-2); }
.gr-rollen-titel { margin: 0; font-size: var(--fs-h3); font-weight: var(--fw-h); color: var(--text); }
.gr-rollen-zahl { color: var(--muted); font-size: var(--fs-sm); }
.gr-rollen-untergruppe { display: flex; flex-direction: column; gap: var(--sp-2); }
.gr-rollen-untertitel { margin: 0; font-weight: var(--fw-medium); color: var(--text); font-size: var(--fs-sm); }
.gr-rollen-liste { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: var(--sp-1); }
.gr-rollen-eintrag {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  padding: var(--sp-2) 0;
  border-bottom: var(--rahmen-breite) solid var(--rahmen-farbe);
}
.gr-rollen-eintrag:last-child { border-bottom: none; }
.gr-rollen-name { font-weight: var(--fw-medium); color: var(--text); overflow-wrap: anywhere; }
.gr-rollen-spacer { flex: 1; }
.gr-rollen-hv-hinweis { color: var(--muted); font-size: var(--fs-xs); }
.gr-rollen-entfernen {
  background: none;
  border: none;
  color: var(--err);
  font: inherit;
  font-size: var(--fs-sm);
  cursor: pointer;
  padding: 0;
  min-height: var(--control-h);
}
.gr-rollen-entfernen:disabled { opacity: .5; cursor: default; }
.gr-rollen-entfernen:focus-visible { outline: 2px solid var(--focus-ring); outline-offset: 2px; }
/* UI-R1b: „ändern“ im HV-Dialog ist neutral (kein Entfernen) — Primärfarbe,
   ohne roten Anstrich. */
.gr-rollen-aendern {
  background: none;
  border: none;
  color: var(--primary);
  font: inherit;
  font-size: var(--fs-sm);
  cursor: pointer;
  padding: 0;
  min-height: var(--control-h);
  text-decoration: underline;
}
.gr-rollen-aendern:focus-visible { outline: 2px solid var(--focus-ring); outline-offset: 2px; }
.gr-rollen-erklaerung { margin: 0; color: var(--muted); font-size: var(--fs-sm); }
.gr-rollen-aktionen { display: flex; flex-wrap: wrap; gap: var(--sp-2); }
.gr-hv { display: flex; flex-direction: column; gap: var(--sp-3); }
.gr-hv-text { margin: 0; color: var(--text); }
.gr-hv-erklaerung { margin: 0; color: var(--muted); font-size: var(--fs-sm); }
.gr-hv-auswahl { display: flex; flex-direction: column; gap: var(--sp-2); }
.gr-hv-gewaehlt { margin: 0; display: flex; align-items: center; gap: var(--sp-2); flex-wrap: wrap; }
.gr-hv-pruefung { margin: 0; font-size: var(--fs-sm); color: var(--muted); }
</style>
