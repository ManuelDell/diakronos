<template>
  <div class="kr-rechte">
    <!-- UI-R2: Freigaben und Sichtbarkeit EINES Kalenders.
         Der Baustein lädt selbst nichts: er zeigt, was ihm die
         Gruppen-Einstellungen übergeben, und meldet jede Änderung nach oben
         (`freigabe-setzen`, `standard-setzen`, `beantragen`,
         `zuruecknehmen`). So kann UI-R3 (Kalenderverwaltung) ihn unverändert
         einbinden und mit ihren eigenen Daten füttern. -->
    <DkSkelett v-if="laedt" form="zeilen" :anzahl="3" text="Freigaben werden geladen …" />

    <DkEmpty
      v-else-if="fehler"
      icon="!"
      title="Freigaben nicht geladen"
      :text="fehler"
      :erneut-versuchen="erneutLaden || null"
    />

    <template v-else>
      <!-- ── Freigaben-Matrix ─────────────────────────────────────────── -->
      <section class="kr-block" data-teil="freigaben">
        <div class="kr-kopf">
          <h4 class="kr-titel">Wer darf diesen Kalender sehen und Termine eintragen</h4>
          <span class="kr-zahl">{{ zeilen.length }}</span>
        </div>
        <p class="kr-hinweis">
          Wer hier steht, sieht den Kalender unabhängig vom Anlegen-Standard
          („{{ standardGruppeLesen ? 'alle Gruppenmitglieder lesen' : 'nur bei Freigabe' }}“).
        </p>

        <DkHint variant="info">
          Jede Änderung gilt sofort — niemand muss sich neu anmelden.
        </DkHint>

        <!-- Die Matrix ist am HANDY KEINE Tabelle: DkTable hat eine
             Mindestbreite (640px) und scherte dort den Kopf ab. Hier wird sie
             zu einer Liste — je Zeile eine Karte mit Name und Schaltern. Am
             Laptop bleibt die Tabelle (dieselben Serverdaten, dieselben
             Endpunkte). Gerätelage aus `istHandyLage`, nie aus der Breite. -->
        <ul v-if="zeilen.length && istHandyLage" class="kr-zeilen">
          <li v-for="z in zeilen" :key="z.art + ':' + z.kennung" class="kr-zeile" :data-freigabe="z.kennung">
            <div class="kr-zeile-kopf">
              <span class="kr-name">{{ z.anzeige }}</span>
              <DkBadge variant="neutral">{{ z.art === 'gruppe' ? 'Gruppe' : 'Person' }}</DkBadge>
            </div>
            <div class="kr-zeile-stufen">
              <!-- UI-R2d: je Stufe ein `<label>`, das sein Kästchen UND sein
                   Wort umschließt (Wort direkt daneben). Eine Stufe, die die
                   Zeile nicht trägt, bekommt KEIN Feld — kein leerer Platz in
                   der Reihe (`handyStufen`). -->
              <template v-for="(feld, i) in stufenFelderDerZeile(z, gezeigteStufen)" :key="i">
                <label v-if="feld" class="kr-stufe-feld">
                  <DkCheckbox
                    :model-value="Boolean(z[feld.stufe])"
                    :aria-label="`${z.anzeige}: ${feld.wort}`"
                    :disabled="feld.gesperrt"
                    @update:model-value="(wert) => stufeSetzen(z, feld.stufe, wert)"
                  />
                  <span class="kr-stufe-wort">{{ feld.wort }}</span>
                </label>
                <!-- UI-R2c: die Zeile trägt die Stufe nicht — dann steht auch in
                     der Liste KEIN Kästchen (kein „Moderieren“ zum Ankreuzen,
                     das die Zeile gar nicht hat). -->
              </template>
            </div>
            <button
              v-if="!nurAnzeigen && lageDerZeile(z).entfernen"
              type="button"
              class="kr-entfernen"
              :aria-label="`${z.anzeige} entfernen`"
              :disabled="zeileGesperrt(z)"
              @click="freigabeEntfernen(z)"
            >Entfernen</button>
            <!-- UI-R2c: der Grund braucht eine EIGENE Bedingung. Im `v-else`
                 des Knopfes stünde er auch bei `nurAnzeigen` — dort ist er
                 immer leer, und ein leeres <p> zieht nur Abstand. -->
            <p v-else-if="!nurAnzeigen && lageDerZeile(z).entfernenHinweis" class="kr-grund">{{ lageDerZeile(z).entfernenHinweis }}</p>
          </li>
        </ul>

        <!-- Tabelle: Kopf und Zeilen tragen DIESELBEN Spalten (Name · Lesen ·
             Schreiben · [Moderieren] · Aktion). „Moderieren“ steht nur im Kopf,
             wenn die Zeilen es zeigen — sonst stünden vier Zellen unter fünf
             Spalten (Review UI-R2b, Punkt 5). `aktion: true` schaltet DkTable
             auf `table-layout: fixed`, damit die Spalten untereinander stehen. -->
        <DkTable
          v-else-if="zeilen.length"
          :spalten="spalten"
          leer-titel="Noch keine Freigabe"
        >
          <tr v-for="z in zeilen" :key="z.art + ':' + z.kennung" :data-freigabe="z.kennung">
            <td>
              <span class="kr-name"><template v-for="(teil, i) in namenTeile(z.anzeige)" :key="i"><wbr v-if="i" />{{ teil }}</template></span>
              <DkBadge variant="neutral">{{ z.art === 'gruppe' ? 'Gruppe' : 'Person' }}</DkBadge>
            </td>
            <td v-for="stufe in gezeigteStufen" :key="stufe" class="kr-stufe">
              <DkCheckbox
                v-if="stufeDerZeile(z, stufe)"
                :model-value="Boolean(z[stufe])"
                :aria-label="`${z.anzeige}: ${stufeLabel(stufe)}`"
                :disabled="zeileGesperrt(z, stufe)"
                @update:model-value="(wert) => stufeSetzen(z, stufe, wert)"
              />
              <!-- UI-R2c: die Zeile trägt diese Stufe gar nicht (eine Zeile
                   ohne Prüfrecht bei gezeigtem „Moderieren“). Die Zelle bleibt
                   als Platzhalter stehen, damit die Spalten untereinander
                   stehen — leer, ohne Bedienelement. -->
              <span v-else class="kr-stufe-leer" aria-hidden="true">–</span>
            </td>
            <td class="kr-aktion">
              <button
                v-if="!nurAnzeigen && lageDerZeile(z).entfernen"
                type="button"
                class="kr-entfernen"
                :aria-label="`${z.anzeige} entfernen`"
                :disabled="zeileGesperrt(z)"
                @click="freigabeEntfernen(z)"
              >Entfernen</button>
              <!-- UI-R2c: eigener Zweig — im `v-else` stünde der Grund auch bei
                   `nurAnzeigen`, wo er immer leer ist. -->
              <span v-else-if="!nurAnzeigen && lageDerZeile(z).entfernenHinweis" class="kr-grund">{{ lageDerZeile(z).entfernenHinweis }}</span>
            </td>
          </tr>
        </DkTable>

        <!-- Leerzustand OHNE DkEmpty: Freigaben erscheinen in der Tabelle
             selbst. So gibt es je Kalender nur EINE Fläche, und eine Tabelle
             mit eigener Leerfläche steht nicht doppelt da. -->
        <p v-else class="kr-leer">
          <span class="kr-leer-symbol" aria-hidden="true">🔒</span>
          <span class="kr-leer-titel">Noch keine Freigabe</span>
          <span class="kr-leer-text">{{ standardHinweis }}</span>
        </p>

        <p class="kr-standard">
          <strong>Alle Gruppenmitglieder:</strong>
          {{ standardGruppeLesen ? 'dürfen standardmäßig lesen' : 'lesen nur mit eigener Freigabe' }}
          <button
            v-if="!nurAnzeigen"
            type="button"
            class="kr-aendern"
            :disabled="busy === standardSchluessel"
            @click="standardUmschalten"
          >{{ standardGruppeLesen ? 'Ändern: nur bei Freigabe' : 'Ändern: alle dürfen lesen' }}</button>
        </p>

        <DkField
          v-if="!nurAnzeigen"
          label="Person oder Gruppe freigeben"
          help="Personen über die Suche, Gruppen aus der Liste. Die Freigabe gilt sofort."
        >
          <div class="kr-hinzufuegen">
            <MitgliedAuswahl
              aria-label="Person für eine Freigabe suchen"
              platzhalter="Name eingeben …"
              :lade-optionen="personenLaden"
              @ausgewaehlt="personHinzufuegen"
            />
            <DkSelect
              v-model="gruppenWahl"
              aria-label="Gruppe für eine Freigabe wählen"
              :options="gruppenOptionen"
              placeholder="Gruppe wählen …"
              :disabled="!gruppenWahlOffen"
            />
            <DkButton
              variant="secondary"
              size="md"
              :disabled="!gruppenWahl || gruppeLaeuft || irgendwasLaeuft"
              :loading="gruppeLaeuft"
              @click="gruppeHinzufuegen"
            >Gruppe freigeben</DkButton>
          </div>
        </DkField>
      </section>

      <!-- ── Sichtbarkeit ─────────────────────────────────────────────── -->
      <section class="kr-block" data-teil="sichtbarkeit">
        <div class="kr-kopf">
          <h4 class="kr-titel">Für alle sichtbar machen</h4>
        </div>

        <p class="kr-sicht-hinweis">
          „Für alle Mitglieder der Gemeinde“ heißt: jedes angemeldete Gemeindemitglied
          sieht den Kalender — auch ohne eigene Freigabe. Bevor der Kalender dort
          erscheint, prüft die Gemeinde den Antrag (Prüfstelle: Gemeinde).
        </p>

        <div v-for="k in sichtbarkeit" :key="k.ziel" class="kr-ziel" :data-ziel="k.ziel">
          <div class="kr-ziel-kopf">
            <span class="kr-ziel-name">{{ k.text }}</span>
            <DkBadge :variant="badgeVariante(k.zustand)">{{ wort(k.zustand) }}</DkBadge>
          </div>
          <p class="kr-ziel-text">{{ k.erklaerung }}</p>
          <div class="kr-ziel-aktionen">
            <DkButton
              v-if="k.beantragen && !nurAnzeigen"
              class="kr-sicht-knopf"
              variant="secondary"
              size="md"
              :disabled="busy === sichtbarkeitSchluessel(k.ziel)"
              :loading="busy === sichtbarkeitSchluessel(k.ziel)"
              @click="$emit('beantragen', k.ziel)"
            >{{ k.text }}</DkButton>
            <DkButton
              v-if="k.zuruecknehmen && !nurAnzeigen"
              class="kr-sicht-knopf"
              variant="ghost"
              size="md"
              :disabled="busy === sichtbarkeitSchluessel(k.ziel)"
              @click="$emit('zuruecknehmen', k.ziel)"
            >Zurücknehmen</DkButton>
          </div>
        </div>
      </section>

      <DkHint v-if="moderierenHinweis" variant="info">{{ moderierenHinweis }}</DkHint>
    </template>
  </div>
</template>

<script setup>
/**
 * KalenderRechte — Freigaben-Matrix und Sichtbarkeit für EINEN Kalender
 * (UI-R2). Reiner Anzeige-Baustein: er lädt nichts und entscheidet nichts
 * über Rechte.
 *
 * Die Oberfläche entscheidet nie über Rechte; sie blendet nur aus, was der
 * Server ohnehin verweigert, und zeigt Serverfehler (403/417) als Satz.
 *
 * Genutzt von:
 *   components/gruppen/KalenderEinstellungen.vue (UI-R2, Gruppen-Einstellungen)
 *   pages/KalenderVerwaltung.vue                (UI-R3, folgt)
 *
 * Datenform (`rechte.get_objekt_rechte`):
 *   { freigaben: [{ benutzer|gruppe, name, lesen, schreiben, moderieren }],
 *     gemeinde_status, gruppe_status, standard_gruppe_lesen, untergruppe,
 *     darf_moderieren_vergeben }
 *
 * `darf_moderieren_vergeben` ist die EINE Quelle für „Moderieren“: es kommt
 * vom Server (dieselbe Regel wie `setze_freigabe`). Fehlt das Feld, gilt
 * `false` — einen Rückfall aus den Rollen der Seite gibt es nicht mehr
 * (UI-R2c: die Prop `darfModerieren` war ein solcher Rückfall und ist tot).
 */
import { computed, ref, watch } from 'vue'
import DkBadge from '../ui/DkBadge.vue'
import DkButton from '../ui/DkButton.vue'
import DkCheckbox from '../ui/DkCheckbox.vue'
import DkEmpty from '../ui/DkEmpty.vue'
import DkField from '../ui/DkField.vue'
import DkHint from '../ui/DkHint.vue'
import DkSelect from '../ui/DkSelect.vue'
import DkSkelett from '../ui/DkSkelett.vue'
import DkTable from '../ui/DkTable.vue'
import MitgliedAuswahl from '../MitgliedAuswahl.vue'
import { useHandyLage } from '../../composables/handyLage.mjs'
import {
  FREIGABE_STUFEN,
  SICHTBARKEIT_WORT,
  busySchluessel,
  freigabeFelder,
  freigabeKnoepfe,
  freigabeZeilen,
  freigabeZeilenLage,
  handyStufen as handyStufenBauen,
  sichtbarkeitKnoepfe,
} from './kalenderRechte.mjs'

const props = defineProps({
  /** Antwort von `rechte.get_objekt_rechte` (null = noch nicht geladen). */
  objekt: { type: Object, default: null },
  /** Kennung des Kalenders (`name`) — sie geht in jede Anfrage. */
  kalender: { type: String, required: true },
  /** Anzeigename, solange der Server noch nichts geliefert hat. */
  titel: { type: String, default: '' },
  /** Untergruppe des Kalenders (leer bei Kalendern der Hauptgruppe). */
  untergruppe: { type: String, default: '' },
  /** Ladezustand der Freigaben. */
  laedt: Boolean,
  /** Fehlertext der Freigaben (leer = keiner). */
  fehler: { type: String, default: '' },
  /** Laufende Aktion (Schlüssel aus `busySchluessel`) — sperrt genau diese Zeile. */
  busy: { type: String, default: '' },
  /**
   * UI-R2e: Ist die letzte Aktion DURCHGEGANGEN? `null` = noch keine Aussage
   * (oder gerade keine). Bezogen auf die Gruppenfreigabe: bei `false` bleibt
   * die gewählte Gruppe nach dem Fehlschlag stehen, bei `true`/`null` wird
   * sie geleert. Ohne dieses Feld müsste die Person die Gruppe nach jedem
   * 403/417 neu heraussuchen.
   */
  freigabeGeklappt: { type: Boolean, default: null },
  /** Auswahlliste der (Unter-)Gruppen: [{ name, anzeigename }]. */
  gruppen: { type: Array, default: () => [] },
  /** Personen für die Suche: (suche) => Promise<[{ benutzer, name }]>. */
  personenLaden: { type: Function, default: null },
  /** Nur lesen (UI-R3 kann die Matrix auch anzeigend einbinden). */
  nurAnzeigen: Boolean,
  /** Erneut laden (Fehlerfläche). */
  erneutLaden: { type: Function, default: null },
})

/**
 * Handy-Lage aus der EINEN Quelle (`istHandyLage`) — am Laptop erscheint nie
 * die Handy-Form und umgekehrt. Die Tabelle hat eine Mindestbreite; in der
 * Leistenge-Lage (< 720px) würde sie den Kopf abscheren.
 */
const { istHandyLage } = useHandyLage()

const emit = defineEmits([
  'freigabe-setzen',   // { objekt, art, kennung, lesen, schreiben, moderieren }
  'standard-setzen',   // wert: boolean
  'beantragen',        // ziel: 'gemeinde' | 'gruppe'
  'zuruecknehmen',     // ziel: 'gemeinde' | 'gruppe'
])

/** Die Zeilen der Matrix aus der Serverantwort. */
const zeilen = computed(() => freigabeZeilen(props.objekt?.freigaben))

/** Ja/Nein der Anlege-Frage (Serverfeld; fehlt es, gilt „alle dürfen lesen“). */
const standardGruppeLesen = computed(() => props.objekt?.standard_gruppe_lesen !== false)

/** Sichtbarkeits-Ziele mit Zustand und Erklärsatz. */
const sichtbarkeit = computed(() => sichtbarkeitKnoepfe({
  untergruppe: props.objekt?.untergruppe ?? props.untergruppe,
  gemeinde_status: props.objekt?.gemeinde_status,
  gruppe_status: props.objekt?.gruppe_status,
}))

/**
 * Darf „Moderieren“ vergeben werden? ALLEIN der Server sagt es
 * (`darf_moderieren_vergeben`). Fehlt das Feld, gilt `false` — fail closed,
 * kein Rückfall aus den Rollen der Seite (UI-R2c).
 */
const darfModerierenVergeben = computed(() => Boolean(props.objekt?.darf_moderieren_vergeben))

/**
 * Die Stufen, die die Matrix zeigt. „Moderieren“ steht im KOPF, sobald das
 * Recht besteht ODER irgendeine Zeile es trägt — sonst sähe niemand, wer
 * prüfen darf.
 *
 * UI-R2c: das ist die EINE Quelle für den Kopf UND für die Zellen. Vorher
 * zeichnete der Kopf aus dieser Liste, die Zellen aber aus `stufenDerZeile`
 * (je Zeile) — bei gemischten Zeilen (eine mit, eine ohne „Moderieren“, ohne
 * Vergaberecht) standen dann fünf Kopfspalten über Zeilen mit vier Zellen.
 */
const gezeigteStufen = computed(() => {
  const stufen = FREIGABE_STUFEN.filter((s) => s !== 'moderieren')
  const mitModeration = darfModerierenVergeben.value || zeilen.value.some((z) => z.moderieren)
  return mitModeration ? FREIGABE_STUFEN : stufen
})

/**
 * Spalten der Matrix — Kopf und Zeilen tragen DIESELBE Zahl:
 * Name · [Stufen] · Aktion. Die Stufen-Spalten kommen aus `gezeigteStufen` —
 * für den Kopf UND für die Zellen; je Stufe entscheidet `stufeDerZeile`, ob
 * die Zeile dort ein Kästchen oder den leeren Platzhalter trägt.
 */
const spalten = computed(() => {
  const liste = [{ key: 'name', label: 'Person oder Gruppe' }]
  for (const stufe of gezeigteStufen.value) liste.push({ key: stufe, label: stufeLabel(stufe) })
  liste.push({ key: 'aktion', label: 'Aktion', aktion: true })
  return liste
})

/** „Lesen · Schreiben · Moderieren“ als Kopfzeile der Stufenspalte. */
const STUFEN_TITEL = ['Lesen', 'Schreiben', 'Moderieren']

/** Beschriftung einer Stufe für Vorleseprogramme. */
function stufeLabel(stufe) {
  return STUFEN_TITEL[FREIGABE_STUFEN.indexOf(stufe)] || stufe
}

/** Was darf diese Zeile: schalten, nur anzeigen, entfernen? */
function lageDerZeile(z) {
  return freigabeZeilenLage(z, { darf_moderieren_vergeben: darfModerierenVergeben.value })
}

/**
 * Trägt diese Zeile die Stufe — oder nur den Platzhalter?
 *
 * „Moderieren“ erscheint bei einer Zeile, die es TATSÄCHLICH trägt, immer
 * (auch ohne Vergaberecht: sonst sähe niemand, wer prüfen darf). Mit
 * Vergaberecht ist es in JEDER Zeile bedienbar (man kann es ja vergeben).
 * Alle anderen Stufen stehen in jeder Zeile.
 */
function stufeDerZeile(z, stufe) {
  return stufe !== 'moderieren' || Boolean(z.moderieren) || lageDerZeile(z).modus
}

/**
 * Die Felder einer Handy-Zeile — je gezeigter Stufe eines oder `null`.
 *
 * (Eigener Name: `handyStufen` ist bereits der Import — ein gleichnamiger
 * lokaler Name wird in der Vorlage NICHT aufgelöst, die Schleife bliebe leer.)
 *
 * Die Sperre kommt aus DIESEM Baustein (`zeileGesperrt`), die Reihenfolge aus
 * `gezeigteStufen`; die Anordnung (Wort neben seinem Kästchen, kein leeres
 * Feld) steht in `handyStufen` (kalenderRechte.mjs) und ist dort ohne Browser
 * prüfbar.
 */
function stufenFelderDerZeile(z, stufen) {
  return handyStufenBauen(z, stufen, {
    darf_moderieren_vergeben: darfModerierenVergeben.value,
    nurAnzeigen: props.nurAnzeigen,
  }, (stufe) => zeileGesperrt(z, stufe)).felder
}

/** Die EINEN Schlüssel der laufenden Aktion (gleiches Format wie die Karte). */
function freigabeSchluessel(z) {
  return busySchluessel('freigabe', props.kalender, z.art, z.kennung)
}
const standardSchluessel = computed(() => busySchluessel('standard', props.kalender))
/**
 * Die gewählte Gruppe, deren Freigabe gerade LÄUFT.
 *
 * UI-R2c: der Knopf las den Schlüssel aus `gruppenWahl` — `gruppeHinzufuegen()`
 * leerte die Wahl aber sofort nach dem `emit`, also war der Schlüssel während
 * der Anfrage leer und der Ladezustand erschien nie (Review UI-R2c, MUSS 1).
 * UI-R2d: darum ein eigenes `ref` — es merkt sich die abgeschickte Gruppe und
 * wird erst geleert, wenn `busy` wieder frei ist (der Knopf bleibt so lange
 * gesperrt). Der Schlüssel ist derselbe Bauplan wie beim Senden:
 * `busySchluessel('freigabe', objekt, 'gruppe', kennung)`.
 */
const gesendeteGruppe = ref('')
const gruppeSchluessel = computed(() => (gesendeteGruppe.value
  ? busySchluessel('freigabe', props.kalender, 'gruppe', gesendeteGruppe.value)
  : ''))
/** Läuft gerade DIE Gruppen-Freigabe (Knopf sperrt/zeigt „lädt“)? */
const gruppeLaeuft = computed(() => Boolean(gruppeSchluessel.value
  && (props.busy === gruppeSchluessel.value
    // Zwischen Klick und erster Antwort trägt die Karte noch keinen Schlüssel
    // (`busy` setzt sie im selben Zug). Ohne diese Bedingung wäre der Knopf
    // für einen Wimpernschlag bedienbar — genau das Fenster des Doppelklicks.
    || !props.busy)))
/**
 * Die Auswahl lässt sich ändern, solange keine Freigabe läuft.
 *
 * UI-R2e: auch NICHT, während eine FREMDE Aktion läuft (`busy` gesetzt, aber
 * nicht der Gruppen-Schlüssel). Sonst ließe sich eine Gruppe wählen, deren
 * Freigabe `freigabeSetzen` mit `if (busy.value) return` still verwarf.
 *
 * `props.busy` ausdrücklich über `props` (nicht über den nackten Namen): im
 * Template würde `busy` sonst die gleichnamige `ref` des Bausteins treffen.
 */
const gruppenWahlOffen = computed(() => !gruppeLaeuft.value && !props.busy)
/** Läuft irgendeine Aktion dieser Fläche (auch eine fremde)? */
const irgendwasLaeuft = computed(() => Boolean(props.busy))

watch(() => props.busy, (wert, vorher) => {
  // Die Antwort ist da (oder die Aktion abgebrochen): Platz für die nächste
  // Gruppe. Ein Fehlschlag räumt `busy` in der Karte ebenfalls ab.
  //
  // UI-R2e: Geleert wird die Auswahl NUR, wenn die Gruppenfreigabe
  // durchging. Scheiterte sie (403/417/Netz), bleibt die gewählte Gruppe
  // stehen — sonst müsste die Person sie nach jedem Fehlschlag neu suchen,
  // obwohl sie dasselbe noch einmal versuchen will.
  if (!wert && gesendeteGruppe.value) {
    const geklappt = props.freigabeGeklappt !== false
    gesendeteGruppe.value = ''
    if (geklappt) gruppenWahl.value = ''
  }
  void vorher
})
function sichtbarkeitSchluessel(ziel) {
  return busySchluessel('sichtbarkeit', props.kalender, ziel)
}

/**
 * Ist diese Zeile (bzw. diese Stufe) gerade gesperrt?
 *
 * `busy` trägt den Schlüssel der laufenden Aktion — die Zeile wartet auf ihre
 * Antwort, ein zweiter Klick sendete doppelt. Zusätzlich ist „Moderieren“
 * ohne Vergaberecht nur ANZEIGE (nicht bedienbar) und bei `nurAnzeigen` ist
 * alles schreibgeschützt.
 */
function zeileGesperrt(z, stufe = '') {
  if (props.nurAnzeigen) return true
  // UI-R2d: die Sperre der ABGESCHICKTEN Gruppe hängt nicht mehr an der Auswahl
  // (`gruppeSchluessel` bleibt während der Anfrage gesetzt, s. o.).
  if (props.busy && (props.busy === freigabeSchluessel(z) || props.busy === gruppeSchluessel.value)) return true
  if (stufe === 'moderieren') return !lageDerZeile(z).modus
  // UI-R2c: „Lesen“ einer Zeile MIT Prüfrecht ist ohne Vergaberecht gesperrt.
  // Der Server setzt bei `moderieren=True` immer `lesen=True` mit (R-12p) —
  // ein Klick nähme das Lesen weg, und der Server setzte es sofort wieder: die
  // Fläche behauptete etwas, das nie eintritt.
  if (stufe === 'lesen') return Boolean(z.moderieren) && !lageDerZeile(z).modus
  return false
}

/**
 * Ein Anzeigename in umbrechbare Teile: vor „@“ und „.“ darf die Zeile
 * umbrechen, statt eine lange Kennung mitten im Wort zu zerreißen
 * (`rebekka.fink@example.org` bleibt so lesbar).
 */
function namenTeile(anzeige) {
  return String(anzeige ?? '').split(/(?=[@.])/).filter((t) => t !== '')
}

/** Hinweis, warum „Moderieren“ nicht bedienbar ist (ein Satz, einmal). */
const moderierenHinweis = computed(() => (darfModerierenVergeben.value
  ? ''
  : freigabeKnoepfe({ darf_moderieren_vergeben: false }).hinweis))

/** Wort eines Zustands (aus/beantragt/aktiv). */
function wort(zustand) {
  return SICHTBARKEIT_WORT[zustand] || SICHTBARKEIT_WORT.aus
}

/** Kennzeichen-Farbe je Zustand. */
function badgeVariante(zustand) {
  if (zustand === 'aktiv') return 'ok'
  if (zustand === 'beantragt') return 'warn'
  return 'neutral'
}

/** Sichtbarer Text, wenn noch keine Freigabe besteht. */
const standardHinweis = computed(() => (standardGruppeLesen.value
  ? 'Alle Gruppenmitglieder dürfen diesen Kalender lesen.'
  : 'Niemand sieht diesen Kalender, solange niemand hier eingetragen ist.'))

/** Auswahl der Gruppen für die Freigabe (ohne die schon eingetragenen). */
const gruppenOptionen = computed(() => {
  const schon = new Set(zeilen.value.map((z) => z.gruppe).filter(Boolean))
  return (Array.isArray(props.gruppen) ? props.gruppen : [])
    .filter((g) => g && g.name && !schon.has(String(g.name)))
    .map((g) => ({ value: String(g.name), label: g.anzeigename || String(g.name) }))
})
const gruppenWahl = ref('')

/** EINE Stelle, die eine Freigabe-Anfrage baut (Kästchen, Entfernen, Hinzufügen). */
function senden(zeile, stufen) {
  const felder = freigabeFelder(zeile, stufen, { darf_moderieren_vergeben: darfModerierenVergeben.value })
  emit('freigabe-setzen', {
    objekt: props.kalender,
    art: zeile.art,
    kennung: zeile.kennung,
    ...felder,
  })
}

/** Ein Kästchen umschalten — die Freigabe gilt sofort. */
function stufeSetzen(zeile, stufe, wert) {
  if (zeileGesperrt(zeile, stufe)) return
  const nachher = {
    lesen: zeile.lesen,
    schreiben: zeile.schreiben,
    moderieren: zeile.moderieren,
    [stufe]: Boolean(wert),
  }
  // „Schreiben“ ohne „Lesen“ ergibt keinen Sinn: wer eintragen darf, sieht
  // den Kalender auch. Der Server verlangt es nicht, die Karte sagt es.
  if (stufe === 'schreiben' && wert) nachher.lesen = true
  // Lesen entziehen nimmt Schreiben mit. Das ANGEZEIGTE „Moderieren“ ebenso —
  // aber nur, wenn es nicht ohnehin gesperrt ist: ohne Vergaberecht ist das
  // Lesen-Häkchen einer moderierenden Zeile nicht bedienbar (`zeileGesperrt`),
  // weil der SERVER bei `moderieren=True` immer `lesen=True` mitsetzt (R-12p):
  // ein Lesen=false käme dort nie an. MIT Vergaberecht bleibt `nachher` beim
  // bisherigen Stand von „Moderieren“ — und `freigabeFelder`
  // (kalenderRechte.mjs) sendet `moderieren = neu.moderieren && lesen`.
  // Folge: „Lesen“ abhaken auf einer moderierenden Zeile entfernt die GANZE
  // Zeile (lesen=false UND moderieren=false) — kein liegen bleibendes
  // Prüfrecht ohne Lesen. Wer nur das Prüfrecht wegnehmen will, hakt
  // „Moderieren“ ab, nicht „Lesen“.
  if (stufe === 'lesen' && !wert) {
    nachher.schreiben = false
    if (!darfModerierenVergeben.value) nachher.moderieren = false
  }
  senden(zeile, nachher)
}

/** „Entfernen“ ist alles-aus (Serverregel: alles false = entfernen). */
function freigabeEntfernen(zeile) {
  if (!lageDerZeile(zeile).entfernen || zeileGesperrt(zeile)) return
  senden(zeile, { lesen: false, schreiben: false, moderieren: false })
}

/** Person aus der Suche hinzufügen: erst Lesen, der Rest nach Bedarf. */
function personHinzufuegen(person) {
  if (!person?.benutzer || props.nurAnzeigen) return
  emit('freigabe-setzen', {
    objekt: props.kalender,
    art: 'person',
    kennung: String(person.benutzer),
    lesen: true,
    schreiben: false,
    moderieren: false,
  })
}

/**
 * Gruppe aus der Liste hinzufügen.
 *
 * UI-R2d: die Wahl wird NICHT mehr sofort geleert. Der Ladezustand des Knopfes
 * hängt an der abgeschickten Gruppe (`gesendeteGruppe`), und die Auswahl bleibt
 * während der Anfrage stehen (gesperrt) — so sieht man, WELCHE Gruppe gerade
 * freigegeben wird. Geleert wird sie erst, wenn `busy` wieder frei ist (watch
 * oben). Vorher war `gruppenWahl` direkt nach dem `emit` leer: der Schlüssel
 * fiel weg, der Knopf zeigte nie „lädt“ und ein zweiter Klick sendete doppelt.
 */
function gruppeHinzufuegen() {
  if (gruppeLaeuft.value) return
  if (!gruppenWahl.value || props.nurAnzeigen) return
  gesendeteGruppe.value = String(gruppenWahl.value)
  emit('freigabe-setzen', {
    objekt: props.kalender,
    art: 'gruppe',
    kennung: String(gruppenWahl.value),
    lesen: true,
    schreiben: false,
    moderieren: false,
  })
}

/** Ja/Nein der Anlege-Frage umschalten. */
function standardUmschalten() {
  if (props.nurAnzeigen) return
  emit('standard-setzen', !standardGruppeLesen.value)
}
</script>

<style scoped>
.kr-rechte { display: flex; flex-direction: column; gap: var(--sp-4); }
.kr-block { display: flex; flex-direction: column; gap: var(--sp-3); }
.kr-kopf { display: flex; align-items: baseline; gap: var(--sp-2); }
.kr-titel { margin: 0; font-size: var(--fs-sm); font-weight: var(--fw-medium); color: var(--text); }
.kr-zahl { color: var(--muted); font-size: var(--fs-xs); }
.kr-name { margin-right: var(--sp-2); overflow-wrap: break-word; }
.kr-stufe { text-align: center; }
/** Platzhalter einer Stufe, die DIESE Zeile nicht trägt (Spalten bleiben). */
.kr-stufe-leer { color: var(--muted); }
/** Grund, warum eine Zeile nicht entfernt werden darf (ein Satz, kein Knopf). */
.kr-grund { margin: 0; color: var(--muted); font-size: var(--fs-xs); }
.kr-aktion { text-align: right; }
.kr-entfernen {
  background: none;
  border: none;
  color: var(--err);
  font: inherit;
  font-size: var(--fs-sm);
  cursor: pointer;
  padding: 0;
  min-height: var(--control-h);
}
.kr-entfernen:disabled { color: var(--muted); cursor: default; }
.kr-standard { margin: 0; font-size: var(--fs-sm); color: var(--muted); display: flex; flex-wrap: wrap; align-items: center; gap: var(--sp-2); }
.kr-aendern {
  background: none;
  border: none;
  color: var(--link);
  font: inherit;
  font-size: var(--fs-sm);
  cursor: pointer;
  padding: 0;
  text-decoration: underline;
  min-height: var(--control-h);
}
.kr-hinzufuegen { display: flex; flex-wrap: wrap; align-items: flex-start; gap: var(--sp-2); }
.kr-ziel { display: flex; flex-direction: column; gap: var(--sp-2); padding: var(--sp-3) 0; border-top: var(--rahmen-breite) solid var(--rahmen-farbe); }
.kr-ziel:first-of-type { border-top: none; }
.kr-ziel-kopf { display: flex; align-items: center; gap: var(--sp-2); }
.kr-ziel-name { font-weight: var(--fw-medium); color: var(--text); }
.kr-ziel-text { margin: 0; color: var(--muted); font-size: var(--fs-sm); }
.kr-ziel-aktionen { display: flex; flex-wrap: wrap; gap: var(--sp-2); }
.kr-sicht-hinweis { margin: 0; color: var(--muted); font-size: var(--fs-sm); }
.kr-hinweis { margin: 0; color: var(--muted); font-size: var(--fs-sm); }
.kr-zeilen { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: var(--sp-3); }
.kr-zeile {
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
  background: var(--surface-2);
  border-radius: var(--radius-lg);
  padding: var(--sp-3);
}
.kr-zeile-kopf { display: flex; flex-wrap: wrap; align-items: center; gap: var(--sp-2); }
.kr-zeile-stufen { display: flex; flex-wrap: wrap; gap: var(--sp-3); }
.kr-stufe-feld { display: inline-flex; align-items: center; gap: var(--sp-2); font-size: var(--fs-sm); color: var(--muted); }
/* UI-R2d: Das ÄUSSERE Label trägt kein Kästchen als direktes Kind (das sitzt
   im DkCheckbox-Label) — die Regel `label:has(> input[type=checkbox])` in
   index.css (Trefferfläche ≥ 44 px, Handy) greift für die INNERE Reihe des
   DkCheckbox und verteilt deren 44 px Mindestbreite als gap zwischen Kästchen
   und Wort (gemessen: 36 px statt 8 px). Die Trefferfläche bleibt: das äußere
   Label umschließt Kästchen und Wort. */
.kr-stufe-feld .dk-ui-checkbox { gap: 0; min-width: 0; }
.kr-leer {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: var(--sp-2);
  background: var(--surface-2);
  border-radius: var(--radius-lg);
  padding: var(--sp-3);
}
.kr-leer-symbol { flex: none; }
.kr-leer-titel { font-weight: var(--fw-medium); color: var(--text); }
.kr-leer-text { color: var(--muted); font-size: var(--fs-sm); }
</style>
