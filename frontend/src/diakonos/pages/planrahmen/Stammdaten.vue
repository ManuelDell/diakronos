<template>
  <div class="dk-screen dk-screen-enter">
    <div class="dk-crumbs">
      <a class="dk-crumb" href="#/dienste/dienstplaene">Dienstpläne</a>
      <span class="dk-crumb-sep" aria-hidden="true">/</span>
      <span class="dk-crumb-current">Stammdaten{{ titelZusatz ? ' — ' + titelZusatz : '' }}</span>
    </div>

    <div class="dk-screen-header">
      <div>
        <h1 class="dk-screen-title">Stammdaten</h1>
        <p class="dk-screen-sub">
          <span v-if="kopfText" class="pr-stamm-kopf">{{ kopfText }}</span>
          <span v-if="planIdGeladen" class="dk-badge dk-badge-brand" title="Bearbeitung im Kontext dieses Plans">Plan-Kontext</span>
          <span v-if="daten && !darfBearbeiten" class="dk-badge">Nur lesen</span>
        </p>
      </div>
      <div class="dk-screen-actions">
        <DkButton
          variant="secondary"
          size="md"
          :disabled="!daten || laden || bedarfLaedt" @click="bedarfOeffnen"
        >{{ bedarfLaedt ? 'Prüfe Bedarf …' : 'Bedarf prüfen' }}</DkButton>
        <DkButton
          variant="secondary"
          size="md"
          :disabled="laden" @click="neuLaden"
        >Neu laden</DkButton>
      </div>
    </div>

    <!-- UX2d3a: Laden zeigt den Umriss (Skelett, erst nach 300 ms), keinen Satz. -->
    <DkSkelett v-if="skelettSichtbar" form="zeilen" :anzahl="6" text="Stammdaten werden geladen …" />

    <div v-else-if="seitenFehler.length" class="pr-stamm-zustand pr-stamm-zustand--fehler">
      <PrMeldungen :meldungen="seitenFehler" />
      <DkButton
        variant="secondary"
        size="md"
        @click="neuLaden"
      >Erneut versuchen</DkButton>
    </div>

    <div v-else-if="!daten" class="dk-empty">
      <p class="dk-empty-title">Keine Planvorlage ausgewählt</p>
      <p class="dk-empty-desc">
        Die Stammdaten hängen an einer Planvorlage. Öffne sie aus der Planübersicht oder aus der Vorbereitung eines Plans.
      </p>
      <DkButton
        variant="secondary"
        size="md"
        as="a"
        href="#/dienste/dienstplaene"
      >Zu den Dienstplänen</DkButton>
    </div>

    <template v-else>
      <!-- PLAN-M1: Hinweis am Handy (nur schmal + Bearbeitungsrecht + nicht
           geschlossen). Sperrt nichts — Ansehen bleibt vollständig möglich. -->
      <PrHandyHinweis
        :sichtbar="handyHinweisZeigen"
        :darf-bearbeiten="darfBearbeiten"
        @geschlossen="handyHinweisSchliessen"
      />

      <!-- ST3: Personenpool-Hinweis — Planer sehen nur die Pool-Personen. -->
      <div v-if="poolInfo && poolInfo.gruppen && poolInfo.gruppen.length" class="pr-stamm-pool">
        <span class="pr-stamm-pool-text">
          Personen aus {{ poolGruppenText }} ({{ poolInfo.anzahl }})
          <template v-if="poolInfo.inkl_untergruppen"> — inklusive Untergruppen</template>.
        </span>
        <a v-if="darfGruppenVerwalten" class="pr-stamm-pool-link"
           :href="'#/gruppe/' + encodeURIComponent(poolInfo.gruppen[0])">Mitglieder der Gruppe verwalten</a>
      </div>

      <div v-if="schreibFehler.length" class="pr-stamm-fehler">
        <PrMeldungen :meldungen="schreibFehler" />
      </div>

      <div class="dk-tab-list" role="tablist" aria-label="Stammdatenbereich wählen">
        <button
          type="button" role="tab" class="dk-tab"
          :class="{ 'is-active': reiter === 'personen' }"
          :aria-selected="reiter === 'personen' ? 'true' : 'false'"
          @click="reiter = 'personen'"
        >Personen &amp; Fähigkeiten<span class="pr-stamm-tab-zahl"> — {{ personenListe.length }} vorhanden</span></button>
        <button
          type="button" role="tab" class="dk-tab"
          :class="{ 'is-active': reiter === 'sammlungen' }"
          :aria-selected="reiter === 'sammlungen' ? 'true' : 'false'"
          @click="reiter = 'sammlungen'"
        >Listen (z. B. Lieder)<span class="pr-stamm-tab-zahl"> — {{ sammlungenListe.length }} vorhanden</span></button>
      </div>

      <!-- ── Personen-Matrix ────────────────────────────────────────────── -->
      <section v-if="reiter === 'personen'" id="pr-stamm-personen" class="pr-stamm-reiter">
        <p class="pr-stamm-hinweis">
          Die Personen kommen aus den Gemeindemitgliedern.
          <template v-if="darfGlobaleBearbeiten">Fehlt jemand? <a href="#/personen">Unter „Personen“ ergänzen</a>.</template>
          <template v-else>Fehlt jemand? Bitte die Mitgliederverwaltung um Ergänzung.</template>
          <template v-if="personenListe.length === 0"> Es sind noch keine Personen vorhanden.</template>
          Markiere in der Tabelle, wer z. B. dirigiert oder Klavier spielt; jede Änderung wird sofort gespeichert.
        </p>
        <p v-if="!personenMerkmale.length" class="pr-stamm-hinweis">
          Diese Planvorlage deklariert keine Fähigkeiten / Eigenschaften — hier gibt es nichts zu pflegen.
        </p>

        <template v-else>
          <div class="pr-stamm-filter">
            <input
              v-model="suche" type="search" class="dk-form-input pr-stamm-suche"
              placeholder="Person suchen (Name, Kürzel) …" aria-label="Personen suchen"
            />
            <select v-model="gruppeWahl" class="dk-form-select pr-stamm-gruppenwahl" aria-label="Nach Gruppe filtern">
              <option value="">Alle Gruppen</option>
              <option v-for="g in gruppenListe" :key="g" :value="g">{{ g }}</option>
            </select>
            <!-- PR-G1: nach Geschlecht filtern (wirkt mit Suche und Gruppe) -->
            <select
              v-model="geschlechtWahl" class="dk-form-select pr-stamm-geschlechtwahl"
              aria-label="Nach Geschlecht filtern"
            >
              <option v-for="o in GESCHLECHT_FILTER" :key="o.value" :value="o.value">{{ o.label }}</option>
            </select>
          </div>

          <!-- Massenaktion: nur explizit ausgewählte Personen -->
          <div v-if="darfGlobaleBearbeiten && auswahlSichtbar.size" class="pr-stamm-masse">
            <span class="pr-stamm-masse-zahl">{{ auswahlSichtbar.size }} {{ auswahlSichtbar.size === 1 ? 'Person' : 'Personen' }} ausgewählt</span>
            <select v-model="massenMerkmal" class="dk-form-select pr-stamm-masse-merkmal" aria-label="Eigenschaft für die Massenaktion">
              <option value="" disabled>Eigenschaft wählen …</option>
              <option v-for="m in personenMerkmale" :key="m.id" :value="m.id">{{ m.name || m.id }}</option>
            </select>
            <div v-if="massenMerkmalDef" class="pr-stamm-masse-wert">
              <MerkmalWert
                :merkmal="massenMerkmalDef" :personen="personenListe"
                v-model="massenWert" @update:model-value="massenBereit = true"
              />
            </div>
            <DkButton
              variant="primary"
              size="md"
              :disabled="!massenMerkmal || !massenBereit || beschaeftigt"
              @click="massenAnwenden"
            >Auf {{ auswahlSichtbar.size }} {{ auswahlSichtbar.size === 1 ? 'Person' : 'Personen' }} anwenden</DkButton>
            <DkButton
              variant="ghost"
              size="md"
              @click="auswahlLeeren"
            >Auswahl aufheben</DkButton>
          </div>

          <div class="pr-stamm-tabelle-wrap">
            <table class="pr-stamm-tabelle">
              <thead>
                <tr>
                  <th class="pr-stamm-spalte-wahl">
                    <input
                      type="checkbox"
                      :checked="alleSichtbarGewaehlt"
                      :disabled="!darfBearbeiten || !gefiltertePersonen.length"
                      aria-label="Alle sichtbaren Personen auswählen"
                      @change="alleSichtbarenUmschalten($event.target.checked)"
                    />
                  </th>
                  <th class="pr-stamm-spalte-name">Person</th>
                  <!-- PR-G1: Spaltenkopf Geschlecht — Klick sortiert (auf → ab → ohne) -->
                  <th
                    class="pr-stamm-spalte-geschlecht"
                    :aria-sort="ariaSortGeschlecht"
                  >
                    <button
                      type="button" class="pr-stamm-sortknopf"
                      :title="sortierTitel" @click="geschlechtSortieren"
                    >
                      Geschlecht<span class="pr-stamm-sortpfeil" aria-hidden="true">{{ sortierPfeil }}</span>
                    </button>
                  </th>
                  <th
                    v-for="m in personenMerkmale" :id="'pr-stamm-mm-' + m.id" :key="m.id"
                    class="pr-stamm-spalte-merkmal"
                    :class="{ 'pr-stamm-spalte--hervor': hervorhebung === 'mm:' + m.id }"
                  >
                    {{ m.name || m.id }}
                    <span class="pr-stamm-art">{{ artText(m) }}</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="p in gefiltertePersonen" :key="p.id" :class="{ 'pr-stamm-zeile--gewaehlt': auswahl.has(p.id) }">
                  <td class="pr-stamm-spalte-wahl">
                    <input
                      type="checkbox"
                      :checked="auswahl.has(p.id)"
                      :disabled="!darfBearbeiten"
                      :aria-label="'Person auswählen: ' + (p.name || p.id)"
                      @change="auswahlUmschalten(p.id, $event.target.checked)"
                    />
                  </td>
                  <td class="pr-stamm-name">
                    <span class="pr-stamm-name-haupt">{{ p.name || p.id }}</span>
                    <span class="pr-stamm-name-neben">
                      <span v-if="p.kuerzel" class="pr-stamm-kuerzel">{{ p.kuerzel }}</span>
                      <span v-for="g in p.gruppen || []" :key="g" class="pr-stamm-gruppen-chip">{{ g }}</span>
                    </span>
                  </td>
                  <!-- PR-G1: Geschlecht klein und ruhig (m/w/d bzw. „–") -->
                  <td class="pr-stamm-geschlecht">
                    <span
                      class="pr-stamm-geschlecht-wert"
                      :class="{ 'pr-stamm-geschlecht--leer': !p.geschlecht }"
                      :aria-label="geschlechtLang(p.geschlecht)"
                      :title="geschlechtLang(p.geschlecht)"
                    >{{ geschlechtKurz(p.geschlecht) }}</span>
                  </td>
                  <td v-for="m in personenMerkmale" :key="m.id" class="pr-stamm-zelle">
                    <MerkmalWert
                      :merkmal="m" :personen="personenListe"
                      :model-value="p.merkmale?.[m.id] ?? null"
                      :readonly="!darfGlobaleBearbeiten || beschaeftigt" kompakt
                      @update:model-value="wertAendern(p, m, $event)"
                    />
                  </td>
                </tr>
                <tr v-if="!gefiltertePersonen.length">
                  <td :colspan="personenMerkmale.length + 3" class="pr-stamm-leer">Keine Personen gefunden.</td>
                </tr>
              </tbody>
            </table>
          </div>
          <!-- PR-G1: viele leere Angaben sichtbar machen (Link nur für Berechtigte) -->
          <p v-if="ohneGeschlechtAnzahl" class="pr-stamm-hinweis pr-stamm-hinweis--geschlecht">
            {{ ohneGeschlechtAnzahl }} {{ ohneGeschlechtAnzahl === 1 ? 'Person' : 'Personen' }} ohne Angabe zum Geschlecht —
            <template v-if="darfGlobaleBearbeiten"><a href="#/personen">unter „Personen“ ergänzen</a>.</template>
            <template v-else>bitte die Mitgliederverwaltung um Ergänzung.</template>
          </p>
        </template>
      </section>

      <!-- ── Listen ─────────────────────────────────────────────────── -->
      <section v-if="reiter === 'sammlungen'" class="pr-stamm-reiter">
        <p v-if="!sammlungenListe.length" class="pr-stamm-hinweis">
          Diese Planvorlage kennt keine Listen — hier gibt es nichts zu pflegen.
        </p>

        <section
          v-for="sam in sammlungenListe" :id="'pr-stamm-sammlung-' + sam.id" :key="sam.id"
          class="pr-stamm-sammlung"
          :class="{ 'pr-stamm-sammlung--hervor': hervorhebung === 'sam:' + sam.id }"
        >
          <div class="pr-stamm-sammlung-kopf">
            <h3 class="pr-stamm-sammlung-titel">{{ sam.name || sam.id }}</h3>
            <span class="dk-badge" :class="sam.umfang === 'plan' ? 'dk-badge-warning' : 'dk-badge-brand'">
              {{ sam.umfang === 'plan' ? 'Plan' : 'Gemeinde' }}
            </span>
            <span v-if="sam.eingebaut" class="dk-badge">Psalmos</span>
            <span class="pr-stamm-anzahl">{{ zeilen(sam.id).length }} {{ zeilen(sam.id).length === 1 ? 'Eintrag' : 'Einträge' }}</span>
            <DkButton
              variant="secondary"
              size="md"
              class="pr-stamm-neu"
              v-if="sammlungNeuErlaubt(sam)" :disabled="beschaeftigt" @click="neuEingabeOeffnen(sam)"
            >Neuer Eintrag</DkButton>
          </div>
          <p v-if="sam.beschreibung" class="pr-stamm-beschreibung">{{ sam.beschreibung }}</p>
          <p v-if="!sammlungEditierbar(sam) && !sam.eingebaut" class="pr-stamm-hinweis">{{ sammlungSperrGrund(sam) }}</p>

          <!-- Eingebaute Liste 'lieder': eigene Pflege-Ansicht (ST2) -->
          <LiederPflege
            v-if="sam.eingebaut"
            :plantyp="geladenerTyp" :plan="planIdGeladen" :definition="definition"
            :darf-bearbeiten="darfBearbeiten" :darf-globale-bearbeiten="darfGlobaleBearbeiten"
            :personen="personenListe" :lieder="zeilen('lieder')"
            @reload="datenNeuLaden"
          />

          <template v-else>
          <p v-if="!sammlungEditierbar(sam)" class="pr-stamm-hinweis">{{ sammlungSperrGrund(sam) }}</p
          >

          <div class="pr-stamm-tabelle-wrap">
            <table class="pr-stamm-tabelle">
              <thead>
                <tr>
                  <th class="pr-stamm-spalte-wahl">
                    <span class="pr-stamm-sr">Reihenfolge</span>
                  </th>
                  <th class="pr-stamm-titel-zelle">Titel</th>
                  <th v-for="m in sammlungMerkmale(sam.id)" :key="m.id" class="pr-stamm-spalte-merkmal">
                    {{ m.name || m.id }}
                    <span class="pr-stamm-art">{{ artText(m) }}</span>
                  </th>
                  <th class="pr-stamm-aktiv"><span class="pr-stamm-sr">Aktiv</span>✓</th>
                </tr>
              </thead>
              <!-- Sortierbares tbody (vue-draggable-plus, v-model wie PrAblauf) -->
              <VueDraggable
                v-model="zeilenProSammlung[sam.id]" tag="tbody"
                handle=".pr-stamm-griff" :animation="150"
                :disabled="!sammlungReorderbar(sam)"
                @end="zeilenUmsortiert(sam, $event)"
              >
                <tr v-for="e in zeilen(sam.id)" :key="e.id" class="pr-stamm-zeile" :class="{ 'pr-stamm-zeile--inaktiv': e.aktiv === false }">
                <td class="pr-stamm-spalte-wahl">
                  <span v-if="sammlungReorderbar(sam)" class="pr-stamm-griff" title="Umsortieren">⠿</span>
                </td>
                <td class="pr-stamm-titel-zelle">
                  <input
                    v-if="!sam.eingebaut && darfBearbeiten"
                    type="text" class="pr-stamm-titel-eingabe"
                    :value="e.daten?.titel || ''"
                    :disabled="beschaeftigt"
                    :aria-label="'Titel bearbeiten: ' + (e.daten?.titel || '')"
                    @change="titelAendern(sam, e, $event.target.value)"
                  />
                  <span v-else class="pr-stamm-titel-text">{{ e.daten?.titel || '–' }}</span>
                </td>
                <td v-for="m in sammlungMerkmale(sam.id)" :key="m.id" class="pr-stamm-zelle">
                  <MerkmalWert
                    :merkmal="m" :personen="personenListe"
                    :model-value="e.merkmale?.[m.id] ?? null"
                    :readonly="!sammlungMerkmaleEditierbar(sam) || beschaeftigt" kompakt
                    @update:model-value="merkmalZeileAendern(sam, m, e, $event)"
                  />
                </td>
                <td class="pr-stamm-aktiv">
                  <input
                    v-if="!sam.eingebaut && darfBearbeiten"
                    type="checkbox"
                    :checked="e.aktiv !== false"
                    :disabled="beschaeftigt"
                    :aria-label="'Eintrag aktiv: ' + (e.daten?.titel || '')"
                    @change="aktivAendern(sam, e, $event.target.checked)"
                  />
                  <span v-else :title="e.aktiv === false ? 'Inaktiv' : 'Aktiv'">{{ e.aktiv === false ? '–' : '✓' }}</span>
                </td>
                </tr>
              </VueDraggable>
            </table>
          </div>
          <p v-if="!zeilen(sam.id).length" class="pr-stamm-hinweis">
            Diese Liste ist noch leer.<template v-if="sammlungNeuErlaubt(sam)"> Lege den ersten Eintrag an.</template>
          </p>

          <!-- Neueingabe für eigene Listen -->
          <div v-if="neuEingabe(sam)" class="pr-stamm-neu">
            <div class="dk-form-group pr-stamm-neu-titel">
              <label :for="'pr-stamm-neu-titel-' + sam.id">Titel</label>
              <input
                :id="'pr-stamm-neu-titel-' + sam.id" type="text" class="dk-form-input"
                :value="neuEingaben[sam.id]?.titel || ''"
                :disabled="beschaeftigt"
                placeholder="z. B. Psalm 23"
                @input="neuTitelSetzen(sam, $event.target.value)"
              />
            </div>
            <div v-for="m in sammlungMerkmale(sam.id)" :key="m.id" class="dk-form-group">
              <label :for="'pr-stamm-neu-' + sam.id + '-' + m.id">{{ m.name || m.id }}</label>
              <MerkmalWert
                :id="'pr-stamm-neu-' + sam.id + '-' + m.id"
                :merkmal="m" :personen="personenListe"
                :model-value="neuEingaben[sam.id]?.merkmale?.[m.id] ?? null"
                :readonly="beschaeftigt"
                @update:model-value="neuMerkmalSetzen(sam, m, $event)"
              />
            </div>
            <div class="pr-stamm-neu-aktionen">
              <DkButton
                variant="secondary"
                size="md"
                @click="neuAbbrechen(sam)"
              >Abbrechen</DkButton>
              <DkButton
                variant="primary"
                size="md"
                :disabled="beschaeftigt || !(neuEingaben[sam.id]?.titel || '').trim()"
                @click="eintragAnlegen(sam)"
              >{{ beschaeftigt ? 'Wird gespeichert …' : 'Anlegen' }}</DkButton>
            </div>
          </div>
          </template>
        </section>
      </section>
    </template>

    <!-- Bedarfsprüfung: einrichten oder überspringen -->
    <BedarfDialog
      v-model="bedarfOffen" :bedarf="bedarfListe" :busy="bedarfLaedt"
      @einrichten="bedarfEinrichten" @ueberspringen="bedarfUeberspringen"
    />
  </div>
</template>

<script setup>
/**
 * Stammdaten-Pflege des Plan-Rahmens (B5): Personen-Matrix (Person × Merkmal)
 * und Sammlungstabellen mit Reihenfolge, Aktiv-Flag und Merkmalen.
 *
 * Kontext kommt aus der Route (UX3a): '#/dienste/vorlagen/<plantyp>'
 * (Plantyp) oder '#/dienste/dienstplaene/vorbereiten/<plan>' (Plan-Kontext — der Plantyp wird
 * vor dem Laden über plan_holen ermittelt). Zusätzlich können plantyp/plan
 * als Props übergeben werden (Einbettung durch den Parent).
 *
 * Alles kommt vom Server: stammdatenHolen liefert Definition, Personen,
 * Sammlungen und das Bearbeitungsrecht; geschrieben wird ausschließlich
 * über merkmale_pflegen (Personen-/Sammlungsmerkmale) und sammlung_pflegen
 * (eigene Sammlungseinträge: anlegen, Titel, aktiv, Reihenfolge).
 * Die Liedstammdaten (Sammlung 'lieder') werden in Psalmos gepflegt — hier
 * sind nur die deklarierten Merkmale editierbar.
 * Umfang 'plan' braucht die konkrete Plan-ID; ohne Plan ist die Sammlung
 * schreibgeschützt (Vorbereitung läuft im Plan).
 */
import { ref, reactive, computed, watch, onMounted, onUnmounted } from 'vue'
import { getRouteParam } from '../../router.js'
import { usePlanrahmen, fehlerMeldungen, datumText } from '../../composables/usePlanrahmen.js'
import { showToast } from '../../composables/useToast.js'
import BedarfDialog from '../../components/planrahmen/BedarfDialog.vue'
import MerkmalWert from '../../components/planrahmen/MerkmalWert.vue'
import PrMeldungen from '../../components/planrahmen/PrMeldungen.vue'
import PrHandyHinweis from '../../components/planrahmen/PrHandyHinweis.vue'
import DkSkelett from '../../components/ui/DkSkelett.vue'
import { useLadeSkelett } from '../../composables/useLadeSkelett.js'
import LiederPflege from '../../components/planrahmen/LiederPflege.vue'
import { useHandyHinweis, hinweisZeigen, istSchmal } from '../../composables/handyHinweis.mjs'
import { VueDraggable } from 'vue-draggable-plus'
import DkButton from '../../components/ui/DkButton.vue'
// PR-G1: Filter/Sortierung nach Geschlecht — gemeinsame Rechnung mit dem Test.
import {
    GESCHLECHT_FILTER, geschlechtKurz, geschlechtLang, anzahlOhneAngabe,
    personenAnzeigen, sortierungUmschalten,
} from './stammdaten-geschlecht.mjs'

const props = defineProps({
  plantyp: { type: String, default: '' },
  plan: { type: String, default: '' },
})

const { stammdatenHolen, planHolen, bedarf, merkmalePflegen, sammlungPflegen } = usePlanrahmen()

// ── Kontext aus Route/Props ────────────────────────────────────────────────

/** Fallback: Hash-Form lesen, falls die Route ohne Parameter-Namen integriert ist. */
function hashKontext() {
    const hash = (typeof window !== 'undefined' && window.location.hash) ? window.location.hash : ''
    // UX3a: neue Adressen zuerst — '#/dienste/vorlagen/‹marke›/stammdaten/‹plantyp›'
    // (die Marke ist ein Platzhalter, der Plantyp steht dahinter) und
    // '#/dienste/dienstplaene/vorbereiten/‹plan›'. Die alten Formen bleiben
    // gültig (Router leitet weiter, diese Datei ist auch einzeln einbettbar).
    let m = hash.match(/^#\/dienste\/vorlagen\/[^/?#]+\/stammdaten\/([^/?#]+)/)
    if (m) return { plantyp: decodeURIComponent(m[1]), plan: '' }
    m = hash.match(/^#\/dienste\/dienstplaene\/vorbereiten\/([^/?#]+)/)
    if (m) return { plantyp: '', plan: decodeURIComponent(m[1]) }
    m = hash.match(/^#\/planrahmen\/stammdaten\/([^/?#]+)/)
    if (m) return { plantyp: decodeURIComponent(m[1]), plan: '' }
    m = hash.match(/^#\/planrahmen\/vorbereiten\/([^/?#]+)/)
    if (m) return { plantyp: '', plan: decodeURIComponent(m[1]) }
    return { plantyp: '', plan: '' }
}
// Der Routen-Parameter kann fehlen (Einbettung, Test-Rand); dann liefert die
// Funktion `undefined` — daraus darf kein Plantyp „undefined“ werden, sonst
// liefe eine Abfrage für einen Typ, den es nicht gibt.
const routePlantyp = computed(() => String(getRouteParam('plantyp') || ''))
const routePlan = computed(() => String(getRouteParam('plan') || ''))
/**
 * Wirksamer Plantyp. Der Platzhalter „-“ aus der Adresse
 * (`#/dienste/vorlagen/-/stammdaten/…`, siehe einrichten-flow.mjs) zählt NICHT
 * als Plantyp — er sagt nur „kein bestimmter Typ in der Adresse“.
 */
const ktxPlantyp = computed(() => {
    const roh = routePlantyp.value || props.plantyp || hashKontext().plantyp || ''
    return roh === '-' ? '' : roh
})
const ktxPlan = computed(() => routePlan.value || props.plan || hashKontext().plan || '')

// ── Ladezustand ────────────────────────────────────────────────────────────

const laden = ref(true)
// UX2d3a: Platzhalter erst, wenn das Laden merklich dauert (300 ms).
const { skelettSichtbar } = useLadeSkelett(laden)
const beschaeftigt = ref(false)
const seitenFehler = ref([])
const schreibFehler = ref([])
const daten = ref(null)
const geladenerTyp = ref('')
const planIdGeladen = ref('')
const planTitel = ref('')
const planZeitraum = ref(null)

const reiter = ref('personen')
const hervorhebung = ref('')

// API→UI-Normalisierung (definition/personen/sammlungen/darf_bearbeiten)
// liegt zentral in usePlanrahmen.stammdatenHolen — hier wird konsumiert.
const definition = computed(() => daten.value?.definition || null)
const darfBearbeiten = computed(() => !!daten.value?.darf_bearbeiten)

// PLAN-M1: Hinweis am Handy — nur schmal + Bearbeitungsrecht + nicht
// geschlossen. Rein Hinweis, nichts wird gesperrt.
const handyHinweis = useHandyHinweis()
const breiteAmFenster = ref(typeof window !== 'undefined' ? window.innerWidth : 0)
const handyHinweisGeschlossen = ref(false)
const handyHinweisZeigen = computed(() => !handyHinweisGeschlossen.value
    && hinweisZeigen({
        schmal: istSchmal(breiteAmFenster.value),
        darfBearbeiten: darfBearbeiten.value,
        geschlossen: false,
    }))
function beiGroessenAenderung() {
    breiteAmFenster.value = typeof window !== 'undefined' ? window.innerWidth : 0
}
function handyHinweisSchliessen() {
    handyHinweis.schliessen()
    handyHinweisGeschlossen.value = true
}
onMounted(() => {
    handyHinweisGeschlossen.value = handyHinweis.geschlossen()
    beiGroessenAenderung()
    if (typeof window !== 'undefined') window.addEventListener('resize', beiGroessenAenderung)
})
const titelZusatz = computed(() => definition.value?.name || geladenerTyp.value || '')
const kopfText = computed(() => {
    const teile = []
    if (definition.value?.name) teile.push(definition.value.name)
    if (planTitel.value) teile.push(planTitel.value)
    if (planZeitraum.value?.von || planZeitraum.value?.bis) {
        teile.push(`${datumText(planZeitraum.value.von, false)} – ${datumText(planZeitraum.value.bis, false)}`)
    }
    return teile.join(' · ')
})

// ST3: Personenpool (gebundene Gruppen) fuer den Hinweis in der Kopfzeile.
const poolInfo = computed(() => daten.value?.pool || null)
const poolGruppenText = computed(() => {
    const namen = poolInfo.value?.namen || []
    return namen.length ? namen.map((n) => '„' + n + '“').join(', ') : ''
})

const merkmaleFuer = (ziel) => {
    const m = definition.value?.merkmale
    return Array.isArray(m?.[ziel]) ? m[ziel] : []
}
const planArg = () => planIdGeladen.value || null

async function neuLaden() { await ladenStarten() }

async function ladenStarten() {
    // Veraltete Antworten schützen: nur die jüngste Anfrage darf den Zustand setzen.
    const nummer = ++ladeNummer
    const aktuell = () => nummer === ladeNummer
    if (!ktxPlantyp.value && !ktxPlan.value) return
    laden.value = true
    seitenFehler.value = []
    schreibFehler.value = []
    planTitel.value = ''
    planZeitraum.value = null
    try {
        let typ = ktxPlantyp.value
        const pid = ktxPlan.value
        if (!typ && pid) {
            // Vorbereitung: erst den Plantyp des Plans ermitteln.
            const pdaten = await planHolen(pid)
            if (!aktuell()) return
            typ = pdaten?.plan?.plantyp || ''
            planTitel.value = pdaten?.plan?.titel || ''
            planZeitraum.value = {
                von: pdaten?.plan?.zeitraum_von || '',
                bis: pdaten?.plan?.zeitraum_bis || '',
            }
            if (!typ) {
                seitenFehler.value = [{
                    pfad: '', code: 'plan_ohne_plantyp',
                    meldung: 'Dieser Plan hat keine Planvorlage — die Stammdaten können nicht geladen werden.',
                    hinweis: '', stufe: 'fehler',
                }]
                return
            }
        }
        const erg = await stammdatenHolen(typ, pid || null)
        if (!aktuell()) return
        daten.value = erg
        geladenerTyp.value = typ
        planIdGeladen.value = pid
        zeilenSpiegeln()
    } catch (err) {
        if (!aktuell()) return
        daten.value = null
        seitenFehler.value = fehlerMeldungen(err)
    } finally {
        if (aktuell()) laden.value = false
    }
}

let ladeNummer = 0
onUnmounted(() => {
    ladeNummer += 1
    if (typeof window !== 'undefined') window.removeEventListener('resize', beiGroessenAenderung)
})

/** Nach Schreibvorgängen neu laden, ohne die Seite neu aufzubauen. */
async function datenNeuLaden() {
    if (!geladenerTyp.value) return
    const n = ladeNummer
    try {
        const erg = await stammdatenHolen(geladenerTyp.value, planArg())
        if (n !== ladeNummer) return
        daten.value = erg
        zeilenSpiegeln()
    } catch (err) {
        if (n === ladeNummer) schreibFehler.value = fehlerMeldungen(err)
    }
}

watch([ktxPlantyp, ktxPlan], ladenStarten, { immediate: true })

// ── Personen-Matrix ────────────────────────────────────────────────────────

const personenListe = computed(() =>
    (Array.isArray(daten.value?.personen) ? daten.value.personen : []))
const personenMerkmale = computed(() => merkmaleFuer('person'))

const suche = ref('')
const gruppeWahl = ref('')
// PR-G1: Geschlechtsfilter — '' (alle), 'm', 'w', 'd' oder 'ohne' (keine Angabe).
const geschlechtWahl = ref('')
const gruppenListe = computed(() => {
    const menge = new Set()
    for (const p of personenListe.value) for (const g of p.gruppen || []) menge.add(g)
    return [...menge].sort((a, b) => String(a).localeCompare(String(b), 'de'))
})
// PR-G1: Suche + Gruppe + Geschlecht wirken zusammen; die Sortierung greift
// auf die gefilterte Liste (siehe `stammdaten-geschlecht.mjs`).
const sortierung = ref({ spalte: '', richtung: 'auf' })
const gefiltertePersonen = computed(() => personenAnzeigen(personenListe.value, {
    suche: suche.value,
    gruppe: gruppeWahl.value,
    geschlecht: geschlechtWahl.value,
    sortierung: sortierung.value,
}))
// Anzahl der Personen OHNE Angabe (Hinweis unter der Tabelle).
const ohneGeschlechtAnzahl = computed(() => anzahlOhneAngabe(personenListe.value))
const geschlechtSortiert = computed(() => sortierung.value.spalte === 'geschlecht')
const ariaSortGeschlecht = computed(() => {
    if (!geschlechtSortiert.value) return 'none'
    return sortierung.value.richtung === 'ab' ? 'descending' : 'ascending'
})
const sortierPfeil = computed(() => {
    if (!geschlechtSortiert.value) return ''
    return sortierung.value.richtung === 'ab' ? ' ▾' : ' ▴'
})
const sortierTitel = computed(() => {
    if (!geschlechtSortiert.value) return 'Nach Geschlecht sortieren (Männer zuerst)'
    return sortierung.value.richtung === 'ab'
        ? 'Sortierung aufheben'
        : 'Umgekehrt sortieren (ohne Angabe zuerst)'
})
function geschlechtSortieren() {
    sortierung.value = sortierungUmschalten(sortierung.value, 'geschlecht')
}

const auswahl = ref(new Set())
function auswahlUmschalten(id, an) {
    const neu = new Set(auswahl.value)
    if (an) neu.add(id)
    else neu.delete(id)
    auswahl.value = neu
}
function auswahlLeeren() { auswahl.value = new Set() }
const alleSichtbarGewaehlt = computed(() =>
    gefiltertePersonen.value.length > 0 && gefiltertePersonen.value.every((p) => auswahl.value.has(p.id)))
function alleSichtbarenUmschalten(an) {
    const neu = new Set(auswahl.value)
    for (const p of gefiltertePersonen.value) {
        if (an) neu.add(p.id)
        else neu.delete(p.id)
    }
    auswahl.value = neu
}
// PR-G1 (Review): Ein Filterwechsel darf keine unsichtbare Auswahl stehen
// lassen — sonst bekäme „alle wählen → auf Männlich filtern → anwenden“ auch
// Frauen die Eigenschaft. Die Auswahl wird auf die sichtbaren Personen
// beschnitten; „N ausgewählt“ zählt danach genau das, was auch wirkt.
const auswahlSichtbar = computed(() => {
    const sichtbar = new Set(gefiltertePersonen.value.map((p) => p.id))
    return new Set([...auswahl.value].filter((id) => sichtbar.has(id)))
})
function auswahlBeschneiden() {
    if (auswahlSichtbar.value.size !== auswahl.value.size) auswahl.value = auswahlSichtbar.value
}
watch([suche, gruppeWahl, geschlechtWahl], auswahlBeschneiden)

// ── Massenaktion (nur explizit ausgewählte Personen) ────────────────────────

const massenMerkmal = ref('')
const massenWert = ref(null)
const massenBereit = ref(false)
const massenMerkmalDef = computed(() =>
    personenMerkmale.value.find((m) => m.id === massenMerkmal.value) || null)

// Merkmal gewechselt → alter Wert gilt nicht mehr für das neue Merkmal.
watch(massenMerkmal, () => {
    massenWert.value = null
    massenBereit.value = false
})

async function massenAnwenden() {
    if (!darfGlobaleBearbeiten.value) return
    const m = massenMerkmalDef.value
    // PR-G1 (Review): doppelt sicher — es wirken NUR Personen, die gerade
    // sichtbar sind (Suche + Gruppe + Geschlecht), auch wenn die Auswahl
    // außerhalb eines Filterwechsels veraltet wäre.
    const ids = [...auswahlSichtbar.value]
    if (!m || !ids.length || !massenBereit.value) return
    const werte = ids.map((id) => ({ ziel: 'person', schluessel: m.id, ziel_id: id, wert: massenWert.value ?? null }))
    await merkmaleSchreiben(werte)
    auswahlLeeren()
    massenMerkmal.value = ''
    massenWert.value = null
    massenBereit.value = false
}

// ── Schreibvorgänge ────────────────────────────────────────────────────────

function meldung(text, stufe = 'fehler', code = '') {
    return [{ pfad: '', code, meldung: text, hinweis: '', stufe }]
}

async function merkmaleSchreiben(werte) {
    if (!werte?.length) return
    schreibFehler.value = []
    beschaeftigt.value = true
    try {
        await merkmalePflegen(geladenerTyp.value, werte, planArg())
        showToast('Stammdaten gespeichert.')
        await datenNeuLaden()
    } catch (err) {
        schreibFehler.value = fehlerMeldungen(err)
    } finally {
        beschaeftigt.value = false
    }
}

function wertAendern(person, merkmal, wert) {
    if (!darfGlobaleBearbeiten.value) return
    return merkmaleSchreiben([{ ziel: 'person', schluessel: merkmal.id, ziel_id: person.id, wert: wert ?? null }])
}

// ── Sammlungen ─────────────────────────────────────────────────────────────

const SAMMLUNG_BUILTIN = new Map([
    ['lieder', { id: 'lieder', name: 'Lieder', umfang: 'gemeinde', eingebaut: true }],
])

/**
 * Sammlungen des Servers in eine Arbeitsform bringen — beide Formen werden
 * akzeptiert: die Map-Form {schluessel: [eintrag, …]} und die Array-Form
 * [{schluessel, name, umfang, eintraege: [{kennung, titel, merkmale, …}]}].
 * Zusatzfelder (aktiv, reihenfolge, daten mit deklarierten Attributen)
 * bleiben erhalten; ohne sie gilt: aktiv=true, Reihenfolge der Liste.
 */
function sammlungenNormalisieren(roh) {
    const karte = new Map()
    if (Array.isArray(roh)) {
        for (const s of roh) {
            if (!s || !s.schluessel) continue
            karte.set(s.schluessel, {
                name: s.name || '',
                umfang: s.umfang || 'gemeinde',
                eingebaut: s.schluessel === 'lieder' || !!s.eingebaut,
                eintraege: Array.isArray(s.eintraege) ? s.eintraege : [],
            })
        }
    } else if (roh && typeof roh === 'object') {
        for (const [key, liste] of Object.entries(roh)) {
            karte.set(key, {
                name: '',
                umfang: 'gemeinde',
                eingebaut: key === 'lieder',
                eintraege: Array.isArray(liste) ? liste : [],
            })
        }
    }
    return karte
}

/** Ein Servereintrag (id/kennung, daten/titel, aktiv, reihenfolge) → Arbeitsform. */
function eintragNormalisieren(e) {
    const datenRoh = (e && typeof e === 'object' && e.daten && typeof e.daten === 'object') ? e.daten : {}
    const daten = { ...datenRoh }
    const titel = e?.titel ?? daten.titel ?? ''
    if (titel !== '' && titel !== undefined && titel !== null) daten.titel = titel
    const basis = {
        id: e?.id ?? e?.kennung ?? null,
        titel: titel ?? '',
        daten,
        reihenfolge: typeof e?.reihenfolge === 'number' ? e.reihenfolge : 0,
        aktiv: e?.aktiv !== false,
        merkmale: { ...(e?.merkmale || {}) },
    }
    // ST2: Material nur fuer Lieder (Server liefert es nur dort) — nicht als
    // leeres Feld erzwingen, sonst aendert sich die Form aller Sammlungen.
    if (Array.isArray(e?.material)) basis.material = e.material
    return basis
}

const sammlungenRoh = computed(() => sammlungenNormalisieren(daten.value?.sammlungen))

const sammlungenListe = computed(() => {
    const karte = new Map()
    for (const s of definition.value?.sammlungen || []) {
        karte.set(s.id, { ...s, eingebaut: s.id === 'lieder' })
    }
    for (const [key, meta] of sammlungenRoh.value) {
        const vorher = karte.get(key) || SAMMLUNG_BUILTIN.get(key) || {}
        karte.set(key, {
            ...vorher,
            id: key,
            name: vorher.name || meta.name || key,
            umfang: vorher.umfang || meta.umfang || 'gemeinde',
            eingebaut: vorher.eingebaut || meta.eingebaut || key === 'lieder',
        })
    }
    return [...karte.values()]
})

const sammlungMerkmale = (schluessel) => merkmaleFuer(schluessel)

// Reaktive Spiegelung der Serverzeilen (v-Muster wie PrAblauf.listen).
const zeilenProSammlung = reactive({})
function zeilenSpiegeln() {
    for (const key of Object.keys(zeilenProSammlung)) delete zeilenProSammlung[key]
    for (const [key, meta] of sammlungenRoh.value) {
        zeilenProSammlung[key] = meta.eintraege.map(eintragNormalisieren)
    }
    // Jede deklarierte Sammlung braucht eine (auch leere) Zeilenliste.
    for (const sam of sammlungenListe.value) {
        if (!Array.isArray(zeilenProSammlung[sam.id])) zeilenProSammlung[sam.id] = []
    }
}
const zeilen = (schluessel) => zeilenProSammlung[schluessel] || []

/** Eigene Sammlungen sind editierbar; 'lieder' nicht (Psalmos); 'plan' braucht die Plan-ID. */
function sammlungEditierbar(sam) {
    if (!darfBearbeiten.value) return false
    if (sam?.eingebaut) return false
    if (sam?.umfang === 'plan') return !!planIdGeladen.value
    return darfGlobaleBearbeiten.value
}
const sammlungNeuErlaubt = sammlungEditierbar
function sammlungReorderbar(sam) { return sammlungEditierbar(sam) && zeilen(sam.id).length > 1 }
function sammlungSperrGrund(sam) {
    if (!darfBearbeiten.value) return 'Ohne Bearbeitungsrecht sind die Stammdaten schreibgeschützt.'
    if (sam?.umfang === 'plan' && !planIdGeladen.value) {
        return 'Diese Liste gehört zu einem konkreten Plan. Die Vorbereitung (Themen usw.) erfolgt im Plan selbst — hier ist sie nur lesbar.'
    }
    if (sam?.eingebaut) return 'Diese Liste wird extern gepflegt — hier sind nur Angaben editierbar.'
    return ''
}

async function sammlungSchreiben(sam, eintraege) {
    schreibFehler.value = []
    beschaeftigt.value = true
    try {
        await sammlungPflegen(geladenerTyp.value, sam.id, eintraege, planArg())
        showToast('Liste gespeichert.')
        await datenNeuLaden()
    } catch (err) {
        // Lokale Reihenfolge/Zeilen auf den Serverstand zurücksetzen.
        zeilenSpiegeln()
        schreibFehler.value = fehlerMeldungen(err)
    } finally {
        beschaeftigt.value = false
    }
}

function zeilenUmsortiert(sam, evt) {
    if (!sammlungEditierbar(sam)) return
    if (evt.oldIndex === evt.newIndex) return
    const liste = zeilen(sam.id)
    if (!liste.length || liste.some((e) => !e?.id)) {
        zeilenSpiegeln()
        showToast('Reihenfolge nicht gespeichert: Eintrag ohne Kennung.')
        return
    }
    // Alle Zeilen mit neuer Positionsnummer — sonst kollidieren
    // gleichbleibende Reihenfolgen der übrigen Einträge.
    return sammlungSchreiben(sam, liste.map((e, i) => ({
        id: e.id,
        daten: e.daten || {},
        reihenfolge: i,
        aktiv: e.aktiv !== false,
    })))
}

function titelAendern(sam, eintrag, roh) {
    if (!sammlungEditierbar(sam) || sam.eingebaut || !eintrag?.id) return
    const titel = String(roh || '').trim()
    if (titel === (eintrag.daten?.titel || '')) return
    return sammlungSchreiben(sam, [{
        id: eintrag.id,
        daten: { ...(eintrag.daten || {}), titel },
        reihenfolge: eintrag.reihenfolge ?? 0,
        aktiv: eintrag.aktiv !== false,
    }])
}

function aktivAendern(sam, eintrag, an) {
    if (!sammlungEditierbar(sam) || sam.eingebaut || !eintrag?.id) return
    return sammlungSchreiben(sam, [{
        id: eintrag.id,
        daten: eintrag.daten || {},
        reihenfolge: eintrag.reihenfolge ?? 0,
        aktiv: !!an,
    }])
}

function merkmalZeileAendern(sam, merkmal, eintrag, wert) {
    if (!sammlungMerkmaleEditierbar(sam) || !eintrag?.id) return
    return merkmaleSchreiben([{ ziel: 'sammlung:' + sam.id, schluessel: merkmal.id, ziel_id: eintrag.id, wert: wert ?? null }])
}

// ── Neueingabe eigener Sammlungen ──────────────────────────────────────────

const neuEingaben = ref({})
const neuEingabe = (sam) => neuEingaben.value[sam.id] || null

function neuEingabeOeffnen(sam) {
    if (!sammlungNeuErlaubt(sam)) return
    if (neuEingaben.value[sam.id]) return
    neuEingaben.value = { ...neuEingaben.value, [sam.id]: { titel: '', merkmale: {} } }
}
function neuAbbrechen(sam) {
    const neu = { ...neuEingaben.value }
    delete neu[sam.id]
    neuEingaben.value = neu
}
function neuTitelSetzen(sam, roh) {
    const eingabe = neuEingaben.value[sam.id]
    if (!eingabe) return
    neuEingaben.value = { ...neuEingaben.value, [sam.id]: { ...eingabe, titel: roh } }
}
function neuMerkmalSetzen(sam, merkmal, wert) {
    const eingabe = neuEingaben.value[sam.id]
    if (!eingabe) return
    neuEingaben.value = {
        ...neuEingaben.value,
        [sam.id]: { ...eingabe, merkmale: { ...eingabe.merkmale, [merkmal.id]: wert } },
    }
}

/** Neuer Eintrag: erst sammlung_pflegen (anlegen), dann merkmale_pflegen. */
async function eintragAnlegen(sam) {
    const eingabe = neuEingaben.value[sam.id]
    if (!eingabe || !sammlungNeuErlaubt(sam)) return
    const titel = String(eingabe.titel || '').trim()
    if (!titel) {
        schreibFehler.value = meldung('Bitte einen Titel eingeben.', 'fehler', 'titel_pflicht')
        return
    }
    schreibFehler.value = []
    beschaeftigt.value = true
    try {
        const liste = zeilen(sam.id)
        const reihenfolge = (liste.length ? Math.max(...liste.map((e) => e.reihenfolge || 0)) : 0) + 1
        const erg = await sammlungPflegen(geladenerTyp.value, sam.id,
            [{ daten: { titel }, reihenfolge, aktiv: true }], planArg())
        const angelegt = Array.isArray(erg?.eintraege) && erg.eintraege.length
            ? erg.eintraege[erg.eintraege.length - 1] : null
        const werte = Object.entries(eingabe.merkmale || {})
            .filter(([, w]) => w !== null && w !== undefined && w !== '')
            .map(([schluessel, wert]) => ({ ziel: 'sammlung:' + sam.id, schluessel, ziel_id: angelegt?.id ?? null, wert }))
        if (werte.length && angelegt?.id) {
            await merkmalePflegen(geladenerTyp.value, werte, planArg())
        }
        neuAbbrechen(sam)
        showToast(angelegt ? 'Eintrag angelegt.' : 'Liste gespeichert.')
        await datenNeuLaden()
    } catch (err) {
        schreibFehler.value = fehlerMeldungen(err)
    } finally {
        beschaeftigt.value = false
    }
}

// ── Bedarfsprüfung ─────────────────────────────────────────────────────────
const darfGlobaleBearbeiten = computed(() => darfBearbeiten.value && daten.value?.darf_globale_stammdaten_bearbeiten !== false)
// ST3: Link 'Mitglieder der Gruppe verwalten' nur fuer Berechtigte.
const darfGruppenVerwalten = computed(() => daten.value?.darf_gruppen_verwalten === true
    || (daten.value?.darf_gruppen_verwalten !== false && darfGlobaleBearbeiten.value))
function sammlungMerkmaleEditierbar(sam) {
    return darfBearbeiten.value && (sam?.umfang === 'plan' ? !!planIdGeladen.value : darfGlobaleBearbeiten.value)
}

const bedarfOffen = ref(false)
const bedarfListe = ref([])
const bedarfLaedt = ref(false)
const uebersprungene = ref(new Set())

async function bedarfOeffnen() {
    if (!geladenerTyp.value) return
    bedarfLaedt.value = true
    schreibFehler.value = []
    try {
        const erg = await bedarf(geladenerTyp.value, planArg())
        bedarfListe.value = Array.isArray(erg) ? erg : []
        bedarfOffen.value = true
    } catch (err) {
        schreibFehler.value = fehlerMeldungen(err)
    } finally {
        bedarfLaedt.value = false
    }
}

let hervorTimer = null
/** Fehlendes Merkmal/Sammlung aus dem Bedarf-Dialog hierher führen. */
function bedarfEinrichten(eintrag) {
    const kennung = eintrag?.kennung
    if (!kennung) return
    if (eintrag.art === 'merkmal') {
        reiter.value = 'personen'
        hervorsetzen('mm:' + kennung)
        springenZu('pr-stamm-mm-' + kennung)
    } else if (eintrag.art === 'sammlung') {
        reiter.value = 'sammlungen'
        hervorsetzen('sam:' + kennung)
        springenZu('pr-stamm-sammlung-' + kennung)
    }
}
function bedarfUeberspringen(eintrag) {
    if (!eintrag?.kennung) return
    uebersprungene.value = new Set(uebersprungene.value).add(eintrag.art + ':' + eintrag.kennung)
    showToast(`„${eintrag.kennung}“ wird übersprungen — hier jederzeit nachpflegbar.`)
}
function hervorsetzen(schluessel) {
    hervorhebung.value = schluessel
    if (hervorTimer) clearTimeout(hervorTimer)
    hervorTimer = setTimeout(() => { hervorhebung.value = '' }, 6000)
}
function springenZu(id) {
    if (typeof document === 'undefined') return
    setTimeout(() => {
        const el = document.getElementById(id)
        if (el && el.scrollIntoView) el.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }, 0)
}

// ── Kleine Helfer ──────────────────────────────────────────────────────────

const ART_NAMEN = {
    tag: 'ja/nein', auswahl: 'Auswahl', text: 'Text', zahl: 'Zahl', datum: 'Datum', person: 'Person',
}
function artText(merkmal) {
    if (merkmal?.art === 'auswahl' && merkmal.mehrfach) return 'mehrfach'
    return ART_NAMEN[merkmal?.art] || merkmal?.art || ''
}
</script>

<style scoped>
.pr-stamm-kopf { margin-right: 10px; }
.pr-stamm-zustand { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; color: var(--dk-text-muted); font-size: var(--fs-14); }
.pr-stamm-zustand--fehler { color: var(--dk-danger); }
.pr-stamm-fehler { margin-bottom: 14px; }
.pr-stamm-reiter { margin-top: 16px; }
.pr-stamm-hinweis { font-size: var(--fs-14); color: var(--dk-text-muted); margin: 8px 0; line-height: 1.5; }
.pr-stamm-pool { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 12px; margin: 4px 0 12px; padding: 10px 14px; border-radius: 10px; background: var(--surface-2); border: 1px solid var(--line); font-size: var(--fs-14); }
.pr-stamm-pool-text { color: var(--text); font-weight: var(--fw-fett); }
.pr-stamm-pool-link { color: var(--primary); text-decoration: underline; }
.pr-stamm-tab-zahl { font-size: var(--fs-12); color: var(--dk-text-subtle); font-weight: var(--fw-normal); }
.pr-stamm-filter { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 12px; }
.pr-stamm-suche { max-width: 320px; }
.pr-stamm-gruppenwahl { max-width: 240px; }
.pr-stamm-geschlechtwahl { max-width: 200px; }
.pr-stamm-masse {
  display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
  padding: 9px 12px; margin-bottom: 12px;
  border: 1px solid color-mix(in oklch, var(--dk-brand-400) 35%, var(--dk-border));
  border-radius: 10px;
  background: color-mix(in oklch, var(--dk-brand-400) 6%, var(--dk-surface));
}
.pr-stamm-masse-zahl { font-size: var(--fs-14); font-weight: var(--fw-fett); color: var(--dk-text); }
.pr-stamm-masse-merkmal { width: auto; min-width: 180px; }
.pr-stamm-masse-wert { min-width: 160px; max-width: 320px; }
.pr-stamm-tabelle-wrap { overflow-x: auto; border: 1px solid var(--dk-border); border-radius: 10px; background: var(--dk-surface); }
.pr-stamm-tabelle { width: 100%; border-collapse: collapse; font-size: var(--fs-14); }
.pr-stamm-tabelle th, .pr-stamm-tabelle td {
  padding: 7px 10px; text-align: left; vertical-align: top;
  border-bottom: 1px solid var(--dk-border);
}
.pr-stamm-tabelle thead th {
  position: sticky; top: 0; z-index: 1;
  background: var(--dk-surface-2); color: var(--dk-text-muted);
  font-size: var(--fs-12); font-weight: var(--fw-fett); text-transform: uppercase; letter-spacing: 0.04em;
  white-space: nowrap;
}
.pr-stamm-tabelle tbody tr:last-child th, .pr-stamm-tabelle tbody tr:last-child td { border-bottom: none; }
.pr-stamm-spalte-wahl { width: 34px; }
.pr-stamm-spalte-wahl input { margin: 2px 0 0; cursor: pointer; }
.pr-stamm-spalte-name { min-width: 180px; }
.pr-stamm-spalte-merkmal { min-width: 120px; }
/* PR-G1: Geschlechtsspalte — schmal, Sortierung über den Spaltenkopf. */
.pr-stamm-spalte-geschlecht { min-width: 5rem; }
.pr-stamm-sortknopf {
  display: inline-flex; align-items: center; gap: 2px;
  padding: 0; border: 0; background: none; color: inherit;
  font-size: inherit; font-weight: inherit; font-family: inherit;
  text-transform: inherit; letter-spacing: inherit; cursor: pointer;
}
.pr-stamm-sortknopf:hover { color: var(--dk-text); }
/* Tippziel am groben Zeiger (Prinzip K4): der Spaltenkopf ist auf dem Handy
   die einzige Sortierfläche; 18 px Höhe wäre zu klein. */
@media (pointer: coarse) { .pr-stamm-sortknopf { min-height: var(--control-h); } }
.pr-stamm-sortknopf:focus-visible {
  outline: 2px solid var(--dk-brand-400); outline-offset: 2px; border-radius: 4px;
}
.pr-stamm-sortpfeil { font-size: var(--fs-12); }
.pr-stamm-geschlecht { min-width: 5rem; }
.pr-stamm-geschlecht-wert {
  display: inline-block; min-width: 18px; text-align: center;
  font-size: var(--fs-12); font-weight: var(--fw-fett); color: var(--dk-text-muted);
}
.pr-stamm-geschlecht--leer { color: var(--dk-text-subtle); font-weight: var(--fw-normal); }
.pr-stamm-spalte--hervor {
  background: color-mix(in oklch, var(--dk-warning) 12%, var(--dk-surface-2));
  transition: background 400ms;
}
.pr-stamm-art { display: block; font-size: var(--fs-12); font-weight: var(--fw-normal); text-transform: none; letter-spacing: 0; color: var(--dk-text-subtle); }
.pr-stamm-zeile--gewaehlt { background: color-mix(in oklch, var(--dk-brand-400) 5%, var(--dk-surface)); }
.pr-stamm-zeile--inaktiv { opacity: 0.55; }
.pr-stamm-name { min-width: 180px; }
.pr-stamm-name-haupt { display: block; font-weight: var(--fw-fett); color: var(--dk-text); }
.pr-stamm-name-neben { display: flex; flex-wrap: wrap; gap: 4px; align-items: baseline; margin-top: 2px; }
.pr-stamm-kuerzel { font-size: var(--fs-12); font-weight: var(--fw-fett); color: var(--dk-accent-d); }
.pr-stamm-gruppen-chip {
  display: inline-block; padding: 0 7px; border-radius: 999px;
  background: var(--dk-surface-2); border: 1px solid var(--dk-border);
  font-size: var(--fs-12); color: var(--dk-text-muted); white-space: nowrap;
  max-width: 180px; overflow: hidden; text-overflow: ellipsis;
}
.pr-stamm-zelle { min-width: 110px; }
.pr-stamm-leer { color: var(--dk-text-muted); font-size: var(--fs-14); padding: 14px 10px; }
.pr-stamm-sammlung + .pr-stamm-sammlung { margin-top: 26px; }
.pr-stamm-sammlung--hervor .pr-stamm-tabelle-wrap,
.pr-stamm-sammlung--hervor .pr-stamm-sammlung-kopf { outline: 2px solid color-mix(in oklch, var(--dk-warning) 55%, transparent); outline-offset: 2px; }
.pr-stamm-sammlung-kopf { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.pr-stamm-sammlung-titel { font-size: var(--fs-16); font-weight: var(--fw-fett); color: var(--dk-text); margin: 0; }
.pr-stamm-anzahl { font-size: var(--fs-12); color: var(--dk-text-muted); }
.pr-stamm-neu { margin-left: auto; }
.pr-stamm-beschreibung { font-size: var(--fs-12); color: var(--dk-text-muted); margin: 4px 0 8px; }
.pr-stamm-griff { cursor: grab; color: var(--dk-text-subtle); user-select: none; flex-shrink: 0; }
.pr-stamm-titel-zelle { min-width: 200px; }
.pr-stamm-titel-eingabe {
  width: 100%; padding: 4px 6px; border-radius: 8px;
  border: 1px solid var(--dk-border); background: var(--dk-surface);
  color: var(--dk-text); font-size: var(--fs-14); font-family: inherit;
}
.pr-stamm-titel-eingabe:focus {
  outline: 2px solid color-mix(in oklch, var(--dk-brand-400) 50%, transparent);
  outline-offset: 0; border-color: var(--dk-brand-400);
}
.pr-stamm-titel-text { font-weight: var(--fw-fett); color: var(--dk-text); }
.pr-stamm-aktiv { width: 56px; text-align: center; color: var(--dk-text-muted); }
.pr-stamm-aktiv input { margin: 2px 0 0; cursor: pointer; }
.pr-stamm-sr {
  position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px;
  overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; border: 0;
}
.pr-stamm-neu {
  display: flex; gap: 14px; flex-wrap: wrap; align-items: flex-end;
  margin-top: 12px; padding: 12px;
  border: 1px dashed var(--dk-border); border-radius: 10px; background: var(--dk-surface-2);
}
.pr-stamm-neu .dk-form-group { margin-bottom: 0; }
.pr-stamm-neu-titel { min-width: 220px; flex: 1; }
.pr-stamm-neu-aktionen { display: flex; gap: 8px; align-items: center; }
</style>
