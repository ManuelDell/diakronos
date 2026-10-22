<template>
  <div class="dk-screen dk-screen-enter">
    <DkPageHeader v-if="!embedded" title="Anfragen" sub="Anfragen, Links & Formulare verwalten" />

    <!-- N2 (Konzept Abschnitt 3, Reiter 3 „Anfragen“): zwei Leitern.
         Oben der Zustand der Anfragen (Offen/Aufgenommen/Abgelehnt), darunter
         die Unterbereiche (Anfragen / Links & QR-Codes / Formulare). Der
         Begriff „Anmeldung“ bleibt dem Login vorbehalten. -->
    <div class="reg-bereich">
      <DkTabs
        v-model="statusTab"
        :options="statusTabs"
        aria-label="Nach Status filtern"
      />
    </div>

    <div class="reg-bereich">
      <DkSegment
        v-model="unterbereich"
        :options="unterbereiche"
        aria-label="Unterbereich"
      />
    </div>

    <!-- Unterbereich 1: Anfragen -->
    <div v-if="unterbereich === 'anfragen'">
      <!-- OP-UI-19: gemeinsames Ladeskelett statt einer eigenen Form. -->
      <DkSkelett v-if="loading" form="tabelle" :anzahl="5" text="Anfragen werden geladen …" />

      <DkCard v-else flach>
        <DkTable
          :spalten="anmeldungSpalten"
          :leer="filteredAnmeldungen.length === 0"
          :leer-titel="leerText"
        >
          <tr v-for="a in filteredAnmeldungen" :key="a.name">
            <td class="reg-jetzt">{{ formatDate(a.anmeldedatum) }}</td>
            <td>{{ a.vorname }} {{ a.nachname }}</td>
            <td>{{ a.anmeldungstyp }}</td>
            <td>
              <!-- OP-ADMIN-7: Dublettenwarnung direkt in der Zeile. Sie kommt
                   aus dem Server (`email_vorhanden`), nicht aus einer im
                   Browser gekappten Mitgliederliste. Kompakt als Kennzeichen
                   (kein Hinweisblock) — die Spalte bleibt so auch am Handy
                   schmal genug. -->
              <DkBadge v-if="istOffen(a) && a.email_vorhanden" variant="warn">
                E-Mail schon vorhanden
              </DkBadge>
              <span v-else class="reg-muted">–</span>
            </td>
            <td><DkBadge :variant="statusVariante(a.status)">{{ a.status }}</DkBadge></td>
            <td>
              <div class="reg-aktionen">
                <DkButton v-if="istOffen(a)"
                  variant="primary" size="sm" :disabled="processing[a.name]" @click="aufnehmen(a)">
                  <IconCheck /> Aufnehmen
                </DkButton>
                <DkButton v-if="istOffen(a)"
                  variant="danger" size="sm" :disabled="processing[a.name]" @click="ablehnen(a)">
                  <IconX /> Ablehnen
                </DkButton>
                <DkButton variant="secondary" size="sm" @click="showDetail(a)">Details</DkButton>
              </div>
            </td>
          </tr>
        </DkTable>
      </DkCard>
    </div>

    <!-- Unterbereich 2: Links & QR-Codes (N3: voller Link, Oeffnen, QR) -->
    <div v-if="unterbereich === 'links'">
      <div class="reg-aktion">
        <DkButton variant="primary" @click="linkOeffnen">
          <IconPlus /> Neuer Link
        </DkButton>
      </div>

      <DkSkelett v-if="loadingLinks" form="karten" :anzahl="3" text="Links werden geladen …" />

      <DkEmpty v-else-if="links.length === 0" title="Keine Registrierungslinks" text="Lege den ersten Link über „Neuer Link“ an." icon="🔗" />

      <div v-else class="reg-grid">
        <DkCard v-for="l in links" :key="l.name" :class="{ 'reg-karte-grau': istAus(l) }">
          <template #header>
            <h2 class="reg-link-titel">{{ l.bezeichnung }}</h2>
          </template>
          <template #actions>
            <DkBadge :variant="zustandVariante(l)">{{ zustandText(l) }}</DkBadge>
            <DkBadge variant="neutral">{{ typKurz(l.typ) }}</DkBadge>
          </template>

          <p v-if="istGastLink(l)" class="reg-link-hinweis">
            Gäste sehen nur Kalender und Profil.
          </p>

          <!-- N3: voller Link, anklickbar; Kopieren/Teilen/Oeffnen/QR. -->
          <RegLinkTeilen :link="l.link_anzeige" :bezeichnung="l.bezeichnung" />

          <!-- N3: Gültigkeit und Plätze sichtbar (Konzept Abschnitt 5). -->
          <div v-if="l.gueltig_bis" class="reg-link-ablauf">
            Gültig bis: {{ formatDate(l.gueltig_bis) }}
          </div>
          <div v-else class="reg-link-meta">Ohne Ablaufdatum</div>

          <div class="reg-link-plaetze">
            <span v-if="l.plaetze_gesamt > 0">
              {{ l.plaetze_belegt }} von {{ l.plaetze_gesamt }} Plätzen belegt
            </span>
            <span v-else>{{ l.plaetze_belegt }} Anmeldungen · ohne Begrenzung</span>
          </div>
          <div
            v-if="l.plaetze_gesamt > 0"
            class="reg-balken"
            role="progressbar"
            :aria-valuenow="l.plaetze_belegt"
            :aria-valuemin="0"
            :aria-valuemax="l.plaetze_gesamt"
          >
            <div class="reg-balken-fuell" :style="{ width: balkenBreite(l) }" />
          </div>
          <div class="reg-link-meta">
            <span v-if="l.anfragen_offen > 0">{{ l.anfragen_offen }} offene {{ l.anfragen_offen === 1 ? 'Anfrage' : 'Anfragen' }}</span>
            <span v-else>Keine offenen Anfragen</span>
          </div>

          <div class="reg-link-aktionen">
            <DkButton v-if="istAus(l)" variant="primary" size="sm" @click="verlaengernOeffnen(l)">
              <IconRefresh /> Verlängern
            </DkButton>
            <DkButton variant="secondary" size="sm" @click="toggleLink(l)">
              {{ l.aktiv ? 'Pausieren' : 'Aktivieren' }}
            </DkButton>
            <DkButton variant="danger" size="sm" @click="deleteLink(l)">Löschen</DkButton>
          </div>
        </DkCard>
      </div>
    </div>

    <!-- Unterbereich 3: Formulare -->
    <div v-if="unterbereich === 'formulare'">
      <div class="reg-aktion">
        <DkButton variant="primary" @click="formularOeffnen">
          <IconPlus /> Neues Formular
        </DkButton>
      </div>

      <DkSkelett v-if="loadingFormulare" form="karten" :anzahl="3" text="Formulare werden geladen …" />

      <DkCard v-else flach>
        <DkTable :spalten="formularSpalten" :leer="formulare.length === 0"
                 leer-titel="Keine Anmeldeformulare vorhanden">
          <tr v-for="f in formulare" :key="f.name">
            <td>{{ f.bezeichnung }}</td>
            <td>{{ f.mit_gaesten ? 'Ja' : 'Nein' }}</td>
            <td>{{ f.mit_kinder ? 'Ja' : 'Nein' }}</td>
            <!-- OP-ADMIN-19: Die Zahl kommt vom Server (`felder_anzahl`); vorher
                 stand hier fest „–“, weil die Kind-Zeilen unsichtbar waren. -->
            <td>{{ f.felder_anzahl }}</td>
            <td class="reg-aktionen">
              <DkButton variant="secondary" size="sm" @click="formularBearbeiten(f)">Bearbeiten</DkButton>
              <DkButton variant="danger" size="sm" @click="formularEntfernen(f)">Löschen</DkButton>
            </td>
          </tr>
        </DkTable>
      </DkCard>
    </div>

    <!-- Dialog: Link erstellen -->
    <DkDialog v-model="showCreateLink" :before-close="linkSchutz.darfSchliessen" title="Neuen Registrierungslink erstellen">
      <form id="reg-link-form" novalidate @submit.prevent="createLink">
       <fieldset class="reg-formular reg-eingaben" :disabled="linkSpeichert">
        <DkHint v-if="linkFehler.speichern" variant="err">{{ linkFehler.speichern }}</DkHint>
        <DkField v-slot="feld" label="Bezeichnung" required :error="linkFehler.bezeichnung">
          <input v-bind="feld" v-model="newLink.bezeichnung" required class="dk-ui-eingabe" placeholder="z. B. Gemeindefest 2026" />
        </DkField>
        <DkField v-slot="feld" label="Typ" required :error="linkFehler.typ">
          <DkSelect v-bind="feld" v-model="newLink.typ" :options="linkTypOptionen" />
        </DkField>
        <DkField label="Gültig bis">
          <input v-model="newLink.gueltig_bis" type="date" class="dk-ui-eingabe"
            :disabled="newLink.ohne_ablauf" />
        </DkField>
        <label class="reg-schalter">
          <input v-model="newLink.ohne_ablauf" type="checkbox" />
          <span>Ohne Ablauf (unbefristet, unabhängig von der Vorgabe)</span>
        </label>
        <DkField label="Max. Anmeldungen" help="0 = unbegrenzt">
          <input v-model.number="newLink.max_anmeldungen" type="number" class="dk-ui-eingabe"
            min="0" :disabled="newLink.unbegrenzt" />
        </DkField>
        <label class="reg-schalter">
          <input v-model="newLink.unbegrenzt" type="checkbox" />
          <span>Unbegrenzt (unabhängig von der Vorgabe)</span>
        </label>
        <DkField label="Anmeldeformular">
          <DkSelect v-model="newLink.anmeldeformular_id" :options="formularOptionen" />
        </DkField>
       </fieldset>
      </form>
      <template #footer>
        <DkButton variant="secondary" :disabled="linkSpeichert" @click="linkSchliessen">Abbrechen</DkButton>
        <DkButton variant="primary" type="submit" form="reg-link-form" :loading="linkSpeichert">Erstellen</DkButton>
      </template>
    </DkDialog>

    <!-- Dialog: Formular erstellen / bearbeiten (OP-ADMIN-19) -->
    <DkDialog v-model="showCreateFormular" :before-close="formularSchutz.darfSchliessen"
              :title="formularBearbeitet ? 'Anmeldeformular bearbeiten' : 'Neues Anmeldeformular'">
      <form id="reg-formular-form" novalidate @submit.prevent="createFormular">
       <fieldset class="reg-formular reg-eingaben" :disabled="formularSpeichert">
        <DkHint v-if="formularFehler.speichern" variant="err">{{ formularFehler.speichern }}</DkHint>
        <DkField v-slot="feld" label="Bezeichnung" required :error="formularFehler.bezeichnung">
          <input v-bind="feld" v-model="newFormular.bezeichnung" required class="dk-ui-eingabe" placeholder="z. B. Standard-Anmeldung" />
        </DkField>
        <div class="reg-kaestchen">
          <DkCheckbox v-model="newFormular.mit_gaesten" label="Mit Gästen" />
          <DkCheckbox v-model="newFormular.mit_kinder" label="Mit Kinder-Option" />
        </div>

        <!-- Felder -->
        <div class="reg-feldbau">
          <div class="reg-feldbau-kopf">
            <span class="reg-feldbau-titel">Felder</span>
            <DkButton variant="secondary" size="sm" @click="addFeld">+ Feld</DkButton>
          </div>
          <div v-for="(f, i) in formularFelder" :key="i" class="reg-feldzeile">
            <DkField v-slot="feld" label="Feldbezeichnung" required :error="formularFehler['reg-feld-' + i]">
              <input v-bind="feld" v-model="f.label" required placeholder="Bezeichnung *" class="dk-ui-eingabe" />
            </DkField>
            <DkSelect v-model="f.feldtyp" :options="feldTypOptionen" aria-label="Feldtyp" />
            <DkCheckbox v-model="f.pflichtfeld" label="Pflicht" />
            <DkButton variant="danger" size="sm" @click="formularFelder.splice(i,1)" aria-label="Feld entfernen">×</DkButton>
          </div>
        </div>
       </fieldset>
      </form>
      <template #footer>
        <DkButton variant="secondary" :disabled="formularSpeichert" @click="formularSchliessen">Abbrechen</DkButton>
        <DkButton variant="primary" type="submit" form="reg-formular-form" :loading="formularSpeichert">
          {{ formularBearbeitet ? 'Speichern' : 'Erstellen' }}
        </DkButton>
      </template>
    </DkDialog>

    <!-- Dialog: Link verlaengern (N3, Konzept Abschnitt 5) -->
    <DkDialog :model-value="!!verlaengernFuer" :title="verlaengernTitel"
              :close-on-overlay="false" :before-close="verlaengernSchutz.darfSchliessen" @update:model-value="verlaengernFuer = null">
      <form v-if="verlaengernFuer" id="reg-verlaengern-form" class="reg-formular" novalidate @submit.prevent="verlaengernBestaetigen">
        <DkHint v-if="verlaengernFehler" variant="err">{{ verlaengernFehler }}</DkHint>
        <DkHint v-if="verlaengernFuer.abgelaufen && verlaengernFuer.voll" variant="warn">
          Der Link ist abgelaufen und das Kontingent ist aufgebraucht. Ein neues
          Datum und mehr Plätze machen ihn wieder benutzbar.
        </DkHint>
        <DkHint v-else-if="verlaengernFuer.abgelaufen" variant="warn">
          Der Link ist abgelaufen. Setze ein neues Datum (oder lass es leer für
          „ohne Ablaufdatum“).
        </DkHint>
        <DkHint v-else-if="verlaengernFuer.voll" variant="warn">
          Alle Plätze sind belegt. Erhöhe die Zahl der Plätze, damit neue
          Anfragen wieder angenommen werden.
        </DkHint>
        <!-- R-N3-main-commits (wichtig 2): „Verlängern“ schaltet den Link
             wieder ein. Bei einem bewusst abgeschalteten Link muss das hier
             stehen, sonst überrascht es. -->
        <DkHint v-if="verlaengernFuer.inaktiv" variant="warn">
          Dieser Link ist ausgeschaltet. Mit „Link verlängern“ wird er wieder
          eingeschaltet — sofort für alle erreichbar.
        </DkHint>

        <DkField v-slot="feld" label="Gültig bis" help="Leer lassen = kein Ablaufdatum.">
          <input :id="feld.id" :aria-describedby="feld['aria-describedby']" v-model="verlaengernDatum" type="date" class="dk-ui-eingabe" />
        </DkField>
        <DkField v-slot="feld" label="Max. Anmeldungen" help="0 = unbegrenzt.">
          <input :id="feld.id" :aria-describedby="feld['aria-describedby']" v-model.number="verlaengernMax" type="number" class="dk-ui-eingabe" min="0" :aria-invalid="!!verlaengernFehler" />
        </DkField>
      </form>
      <template #footer>
        <DkButton variant="secondary" :disabled="verlaengernLaeuft" @click="verlaengernSchliessen">Abbrechen</DkButton>
        <DkButton variant="primary" type="submit" form="reg-verlaengern-form" :loading="verlaengernLaeuft">
          <IconRefresh /> Link verlängern
        </DkButton>
      </template>
    </DkDialog>

    <!-- Konfliktfenster: Löschen bestätigen (N3, kein natives confirm) -->
    <DkDialog :model-value="!!bestaetigenFrage" :title="bestaetigenFrage?.titel || 'Löschen bestätigen'"
              :close-on-overlay="false" @update:model-value="bestaetigenAntwort(false)">
      <p class="reg-dialog-text">{{ bestaetigenFrage?.text }}</p>
      <template #footer>
        <DkButton variant="secondary" @click="bestaetigenAntwort(false)">Abbrechen</DkButton>
        <DkButton variant="danger" @click="bestaetigenAntwort(true)">
          <IconTrash /> Link löschen
        </DkButton>
      </template>
    </DkDialog>

    <!-- Dialog: Anfrage-Details (OP-ADMIN-8: vollständig, Titel mit Name) -->
    <DkDialog :model-value="!!detailAnmeldung" size="md"
              :title="detailAnmeldung ? 'Anfrage von ' + detailName : 'Anfrage'"
              @update:model-value="detailAnmeldung = null">
      <div v-if="detailAnmeldung" class="reg-detail">
        <div class="reg-detail-grid">
          <div><strong>Name:</strong> {{ detailAnmeldung.vorname }} {{ detailAnmeldung.nachname }}</div>
          <div><strong>E-Mail:</strong> {{ detailAnmeldung.email || '–' }}</div>
          <div><strong>Telefon:</strong> {{ detailAnmeldung.telefon || '–' }}</div>
          <div><strong>Geburtstag:</strong> {{ detailAnmeldung.geburtstag ? formatDate(detailAnmeldung.geburtstag) : '–' }}</div>
          <div><strong>Typ:</strong> {{ detailAnmeldung.anmeldungstyp }}</div>
          <div><strong>Status:</strong> <DkBadge :variant="statusVariante(detailAnmeldung.status)">{{ detailAnmeldung.status }}</DkBadge></div>
          <div><strong>Datum:</strong> {{ formatDate(detailAnmeldung.anmeldedatum) }}</div>
          <div v-if="detailAnmeldung.kommentar"><strong>Kommentar:</strong> {{ detailAnmeldung.kommentar }}</div>
        </div>

        <DkHint v-if="emailDublette(detailAnmeldung)" variant="err">
          Diese E-Mail-Adresse gehört bereits zu einer Person. Jede Person
          braucht eine eigene Adresse — bitte zuerst dort die Adresse
          korrigieren; aufnehmen lässt sich die Anfrage so nicht.
        </DkHint>

        <div v-if="detailAnmeldung.antworten?.length" class="reg-detail-abschnitt">
          <h4>Formular-Antworten</h4>
          <dl class="reg-antworten">
            <template v-for="a in detailAnmeldung.antworten" :key="a.label">
              <dt>{{ a.label }}</dt>
              <dd>{{ a.wert || '–' }}</dd>
            </template>
          </dl>
        </div>

        <div v-if="detailAnmeldung.kinder?.length" class="reg-detail-abschnitt">
          <h4>Angemeldete Kinder</h4>
          <ul class="reg-kinder">
            <li v-for="k in detailAnmeldung.kinder" :key="k.vorname">
              {{ k.vorname }} {{ k.nachname }}<span v-if="k.geburtstag" class="reg-kinder-geb"> ({{ k.geburtstag }})</span>
            </li>
          </ul>
        </div>
      </div>
      <template #footer>
        <DkButton variant="secondary" @click="detailAnmeldung = null">Schließen</DkButton>
      </template>
    </DkDialog>

    <!-- Dialog: Aufnehmen (N2). OP-UI-13: Bestätigen statt Ein-Klick-Genehmigen;
         OP-ADMIN-7: Status und Gruppe wählbar. -->
    <DkDialog :model-value="!!aufnehmenFuer" :title="aufnehmenTitel"
              :close-on-overlay="false" :before-close="aufnehmenSchutz.darfSchliessen" @update:model-value="aufnehmenFuer = null">
      <form v-if="aufnehmenFuer" id="reg-aufnehmen-form" novalidate @submit.prevent="aufnehmenBestaetigen">
        <p class="reg-dialog-text">
          <strong>{{ aufnehmenFuer.vorname }} {{ aufnehmenFuer.nachname }}</strong>
          wird als Person angelegt ({{ aufnehmenFuer.email || 'ohne E-Mail' }}).
          Wähle Status und Gruppe.
        </p>
        <DkHint v-if="aufnehmenFuer.dublette" variant="err">
          Es gibt bereits eine Person mit dieser E-Mail-Adresse. Jede Person
          braucht eine eigene Adresse — bitte zuerst die vorhandene Person
          öffnen und dort die Adresse korrigieren.
        </DkHint>
        <!-- M2 (R-N2-code): Hat der Server beim Aufnehmen abgelehnt (z.B.
             Dublette, die in der Zwischenzeit entstanden ist), bleibt das
             Fenster offen und nennt den Grund — sonst sieht die Person nur
             einen flüchtigen Toast und die Liste blieb veraltet. -->
        <DkHint v-if="aufnehmenFehler" variant="err">{{ aufnehmenFehler }}</DkHint>

        <div class="reg-formular">
          <DkField v-slot="feld" label="Status" required>
            <DkSelect :id="feld.id" v-model="aufnehmenStatus" :options="statusOptionen" :invalid="!aufnehmenStatus && !!aufnehmenFehler" />
          </DkField>
          <DkField v-slot="feld" label="Gruppe" help="Leer lassen, wenn keine Gruppe zugewiesen werden soll.">
            <DkSelect :id="feld.id" :aria-describedby="feld['aria-describedby']" v-model="aufnehmenGruppe" :options="gruppeOptionen" empty-value="" />
          </DkField>
        </div>
      </form>
      <template #footer>
        <DkButton variant="secondary" :disabled="aufnehmenLaeuft" @click="aufnehmenSchliessen">Abbrechen</DkButton>
        <DkButton variant="primary" type="submit" form="reg-aufnehmen-form" :loading="aufnehmenLaeuft">
          <IconCheck /> Aufnehmen
        </DkButton>
      </template>
    </DkDialog>

    <!-- Dialog: Ablehnen (OP-UI-13: im App-Fenster, kein natives prompt()) -->
    <DkDialog :model-value="!!ablehnenFuer" title="Anfrage ablehnen"
              :close-on-overlay="false" :before-close="ablehnenSchutz.darfSchliessen" @update:model-value="ablehnenFuer = null">
      <form v-if="ablehnenFuer" id="reg-ablehnen-form" novalidate @submit.prevent="ablehnenBestaetigen">
        <DkHint v-if="ablehnenFehler" variant="err">{{ ablehnenFehler }}</DkHint>
        <p class="reg-dialog-text">
          Anfrage von <strong>{{ ablehnenFuer.vorname }} {{ ablehnenFuer.nachname }}</strong>
          wirklich ablehnen? Die Person wird damit nicht aufgenommen.
        </p>
        <DkField v-slot="feld" label="Grund (optional)">
          <input :id="feld.id" v-model="ablehnGrund" class="dk-ui-eingabe" placeholder="z. B. keine Kapazität mehr" />
        </DkField>
      </form>
      <template #footer>
        <DkButton variant="secondary" :disabled="ablehnenLaeuft" @click="ablehnenSchliessen">Abbrechen</DkButton>
        <DkButton variant="danger" type="submit" form="reg-ablehnen-form" :loading="ablehnenLaeuft">
          <IconX /> Ablehnen
        </DkButton>
      </template>
    </DkDialog>

  </div>
</template>

<script setup>
/**
 * Anfragen — Anfragen/Links/Formulare im Design-System (N2).
 *
 * Reiter „Anfragen“ des Mitglieder-Bereichs (Konzept Abschnitt 3, Reiter 3).
 * Aufbau: oben der Status der Anfragen (Offen mit Zähler / Aufgenommen /
 * Abgelehnt), darunter die Unterbereiche Anfragen, Links & QR-Codes und
 * Formulare. Das Wort „Anmeldung“ bleibt dem Login vorbehalten.
 *
 * OP-ADMIN-7: Aufnehmen ist kein Ein-Klick-Vorgang mehr. Das Fenster zeigt
 * Name, E-Mail und den Dublettenhinweis und lässt Status und Gruppe wählen.
 * Die Dublettenwarnung kommt aus dem Server (`email_vorhanden`), nicht aus
 * einer im Browser gekappten Mitgliederliste.
 * OP-ADMIN-8: Die Detailansicht zeigt Telefon, Geburtstag und Kommentar und
 * nennt den Namen im Titel statt einer rohen ID.
 *
 * Rechte kommen vom Server (admin_hub prüft „Mitgliederadministrator“); hier
 * wird nichts sicherheitsrelevant ein- oder ausgeblendet.
 */
import { ref, computed, onMounted, h } from 'vue'
import { apiCall } from '../composables/useApi.js'
import { showToast } from '../composables/useToast.js'
import { useFormularSchutz } from '../composables/useFormularSchutz.js'
import { pflichtFehler } from '../composables/formularPruefung.mjs'

// Im Mitglieder-Bereich eingebettet: eigener Kopf entfällt.
defineProps({ embedded: { type: Boolean, default: false } })
import DkPageHeader from '../components/ui/DkPageHeader.vue'
import DkButton from '../components/ui/DkButton.vue'
import DkBadge from '../components/ui/DkBadge.vue'
import DkCard from '../components/ui/DkCard.vue'
import DkDialog from '../components/ui/DkDialog.vue'
import DkTabs from '../components/ui/DkTabs.vue'
import DkSegment from '../components/ui/DkSegment.vue'
import DkField from '../components/ui/DkField.vue'
import DkSelect from '../components/ui/DkSelect.vue'
import DkCheckbox from '../components/ui/DkCheckbox.vue'
import DkTable from '../components/ui/DkTable.vue'
import DkEmpty from '../components/ui/DkEmpty.vue'
import DkSkelett from '../components/ui/DkSkelett.vue'
import DkHint from '../components/ui/DkHint.vue'
import RegLinkTeilen from '../components/registrierung/RegLinkTeilen.vue'

const loading = ref(true)
const loadingLinks = ref(true)
const loadingFormulare = ref(true)
const anmeldungen = ref([])
const links = ref([])
const formulare = ref([])
const gruppenAuswahl = ref([])
const processing = ref({})
// N3: Warnungen laufen über den globalen Toast (useToast) — der frühere
// eigene .reg-toast kannte keinen Warn-Stil (Befund R-N2-code 5) und war eine
// zweite Umsetzung neben useToast.

/** Bestätigung im App-Fenster (Ergebnis via Promise) — kein natives confirm(). */
const bestaetigenFrage = ref(null)
let bestaetigenLoesen = null
function bestaetigen(titel, text) {
  bestaetigenFrage.value = { titel, text }
  return new Promise((loesen) => { bestaetigenLoesen = loesen })
}
function bestaetigenAntwort(wert) {
  bestaetigenFrage.value = null
  const loesen = bestaetigenLoesen
  bestaetigenLoesen = null
  if (loesen) loesen(wert)
}

/** OP-ADMIN-7: Statuswerte der Anfrage, die als „offen“ gelten. */
const OFFENE_ANMELDESTATI = ['Anmeldeanfrage', 'Ausstehend']

/** Unterbereich (Konzept-Reiter 3): Anfragen | Links & QR-Codes | Formulare. */
const unterbereich = ref('anfragen')
const unterbereiche = [
  { value: 'anfragen', label: 'Anfragen' },
  { value: 'links',    label: 'Links & QR-Codes' },
  { value: 'formulare', label: 'Formulare' },
]

/** Statusleiter der Anfragen (Konzept-Reiter 3). */
const statusTab = ref('offen')
const statusTabs = computed(() => [
  { value: 'offen',     label: `Offen (${zaehle('offen')})` },
  { value: 'genehmigt', label: 'Aufgenommen' },
  { value: 'abgelehnt', label: 'Abgelehnt' },
])

function zaehle(art) {
  if (art === 'offen') return anmeldungen.value.filter(istOffen).length
  if (art === 'genehmigt') return anmeldungen.value.filter(a => a.status === 'Bestätigt').length
  if (art === 'abgelehnt') return anmeldungen.value.filter(a => a.status === 'Abgelehnt').length
  return 0
}

/** Ist die Anfrage noch offen (aufnehmbar/ablehnbar)? */
function istOffen(a) {
  return OFFENE_ANMELDESTATI.includes(a.status)
}

const anmeldungSpalten = [
  { key: 'datum', label: 'Datum' },
  { key: 'name', label: 'Name' },
  { key: 'art', label: 'Art' },
  { key: 'hinweis', label: 'Hinweis' },
  { key: 'status', label: 'Status' },
  { key: 'aktionen', label: 'Aktionen' },
]
const formularSpalten = [
  { key: 'bez', label: 'Bezeichnung' },
  { key: 'gaeste', label: 'Gäste' },
  { key: 'kinder', label: 'Kinder' },
  { key: 'felder', label: 'Felder' },
  { key: 'aktionen', label: 'Aktionen' },
]
const linkTypOptionen = [
  { value: 'Mitglied-Registrierung', label: 'Mitglied-Registrierung' },
  { value: 'Gast-Anmeldung', label: 'Gast-Anmeldung' },
  { value: 'Veranstaltung', label: 'Veranstaltung' },
]
const feldTypOptionen = ['Text', 'Zahl', 'Datum', 'Ja-Nein', 'Auswahl']
  .map(t => ({ value: t, label: t }))
const formularOptionen = computed(() => [
  { value: '', label: '– Keines –' },
  ...formulare.value.map(f => ({ value: f.name, label: f.bezeichnung })),
])

/** N2: Statusauswahl beim Aufnehmen (Quelle: mitglieder.MITGLIED_STATUS). */
const statusOptionen = [
  { value: 'Mitglied',         label: 'Mitglied' },
  { value: 'Gast',             label: 'Gast' },
  { value: 'Passives Mitglied', label: 'Passives Mitglied' },
  { value: 'Passiver Gast',    label: 'Passiver Gast' },
]

/** N2: Gruppenauswahl beim Aufnehmen. */
const gruppeOptionen = computed(() => [
  { value: '', label: '– Keine Gruppe –' },
  ...gruppenAuswahl.value.map(g => ({ value: g.name, label: g.gruppenname || g.name })),
])

const filteredAnmeldungen = computed(() => {
  if (statusTab.value === 'offen') return anmeldungen.value.filter(istOffen)
  if (statusTab.value === 'genehmigt') return anmeldungen.value.filter(a => a.status === 'Bestätigt')
  if (statusTab.value === 'abgelehnt') return anmeldungen.value.filter(a => a.status === 'Abgelehnt')
  return anmeldungen.value
})

const leerText = computed(() => {
  if (statusTab.value === 'offen') return 'Keine offenen Anfragen'
  if (statusTab.value === 'genehmigt') return 'Keine aufgenommenen Anfragen'
  if (statusTab.value === 'abgelehnt') return 'Keine abgelehnten Anfragen'
  return 'Keine Anfragen vorhanden'
})

async function fetchData() {
  let anfragenAktuell = false
  loading.value = true
  loadingLinks.value = true
  loadingFormulare.value = true
  try {
    const res = await apiCall('diakronos.diakonos.api.admin_hub.get_anmeldungen_hub')
    anmeldungen.value = res.anmeldungen || []
    anfragenAktuell = true
    links.value = res.links || []
  } catch (err) {
    console.error(err)
    showToast('Fehler beim Laden', 'error')
  } finally {
    loading.value = false
    loadingLinks.value = false
  }

  try {
    const fRes = await apiCall('diakronos.diakonos.api.admin_hub.get_anmeldeformulare')
    formulare.value = fRes.formulare || []
  } catch (err) {
    console.error(err)
  } finally {
    loadingFormulare.value = false
  }

  // N2: Gruppenauswahl für „Aufnehmen“. Die Liste kommt aus der
  // Gruppen-Ansicht (dieselbe Quelle wie überall); sie ist nur Komfort —
  // der Server prüft die konkrete Zuweisung ohnehin beim Aufnehmen nach.
  try {
    const gRes = await apiCall('diakronos.diakonos.api.gruppen.get_gruppen_page_data')
    gruppenAuswahl.value = gRes.gruppen_auswahl || []
  } catch (err) {
    // Ohne Anlege-Rechte liefert der Server eine leere Auswahl — kein Fehler.
    gruppenAuswahl.value = []
  }
  return anfragenAktuell
}

/** OP-ADMIN-7: Dublettenhinweis aus dem Server (`email_vorhanden`). */
function emailDublette(a) {
  return !!(a && (a.email_vorhanden === 1 || a.email_vorhanden === '1' || a.email_vorhanden === true))
}

/** N2: Status beim Aufnehmen aus dem Anmeldungstyp vorbelegen. */
function statusVorschlag(a) {
  return a?.anmeldungstyp === 'Mitglied-Registrierung' ? 'Mitglied' : 'Gast'
}

// ── Aufnehmen (OP-ADMIN-7/OP-UI-13 + N2) ──────────────────────────────────

const aufnehmenFuer = ref(null)
const aufnehmenStatus = ref('Mitglied')
const aufnehmenGruppe = ref('')
const aufnehmenFehler = ref('')
const aufnehmenLaeuft = ref(false)
const aufnehmenSchutz = useFormularSchutz(
  () => [aufnehmenStatus.value, aufnehmenGruppe.value], () => aufnehmenLaeuft.value,
)
async function aufnehmenSchliessen() {
  if (await aufnehmenSchutz.darfSchliessen()) aufnehmenFuer.value = null
}

const aufnehmenTitel = computed(() => {
  const a = aufnehmenFuer.value
  if (!a) return 'Anfrage aufnehmen'
  const name = `${a.vorname || ''} ${a.nachname || ''}`.trim()
  return name ? `Anfrage von ${name} aufnehmen` : 'Anfrage aufnehmen'
})

function aufnehmen(a) {
  aufnehmenStatus.value = statusVorschlag(a)
  // Zielfeld der Anmeldung vorbelegen (OP-ADMIN-8 liefert `gruppe` mit).
  aufnehmenGruppe.value = a.gruppe || ''
  aufnehmenFehler.value = ''
  aufnehmenSchutz.merken()
  aufnehmenFuer.value = { ...a, dublette: emailDublette(a) }
}

async function aufnehmenBestaetigen() {
  const ziel = aufnehmenFuer.value
  if (!ziel || aufnehmenLaeuft.value) return
  aufnehmenFehler.value = ''
  if (!aufnehmenStatus.value) {
    aufnehmenFehler.value = 'Bitte wähle einen Status.'
    fehlerFokussieren('reg-aufnehmen-form')
    return
  }
  const id = ziel.name
  aufnehmenLaeuft.value = true
  processing.value[id] = true
  try {
    // SEC-b (Fachentscheidung 2026-10-19): Eine E-Mail-Adresse gehoert
    // hoechstens zu EINER Person. Das frueher hier mitgeschickte
    // `dublette_bestaetigt` ist damit gegenstandslos — der Server lehnt eine
    // belegte Adresse ohnehin immer ab (siehe Hinweis im Dialog).
    const res = await apiCall('diakronos.diakonos.api.admin_hub.genehmige_anmeldung', {
      anmeldung_id: id,
      status: aufnehmenStatus.value,
      gruppe: aufnehmenGruppe.value || '',
    })
    if (!res.success) throw new Error('Die Anfrage konnte nicht aufgenommen werden. Bitte erneut versuchen.')
    if (res.success) {
      aufnehmenFuer.value = null
      aufnehmenSchutz.merken()
      showToast('Anfrage aufgenommen')
      // B4 (P1-7b): Das Mitglied ist angelegt; einzelne Schritte (z.B. die
      // Zuweisung zur Gruppe) koennen trotzdem fehlschlagen. Der Server meldet
      // sie als `warnungen` — ohne Anzeige bliebe das Mitglied unbemerkt ohne
      // Gruppe.
      for (const w of res.warnungen || []) {
        showToast(w, 'warning')
      }
      await fetchData()
    }
  } catch (err) {
    // M2 (R-N2-code): Der Server kann das Aufnehmen verweigern (z.B. eine
    // Dublette, die seit dem Oeffnen des Fensters entstanden ist). Dann die
    // Liste neu laden und das Fenster mit dem Grund wieder oeffnen, statt die
    // veraltete Zeile stehen zu lassen. P2-1: Der Grund steht sofort und
    // sichtbar im Fenster (aufnehmenFehler), die Eingaben bleiben erhalten.
    aufnehmenFehler.value = err?.message || 'Aufnehmen nicht möglich.'
    let anfragenAktuell = false
    try {
      anfragenAktuell = await fetchData()
    } catch { /* Anzeigefehler darf den Hinweis nicht verdecken */ }
    const frische = anmeldungen.value.find(a => a.name === id)
    if (anfragenAktuell && frische && istOffen(frische)) {
      aufnehmenStatus.value = statusVorschlag(frische)
      aufnehmenGruppe.value = frische.gruppe || ''
      aufnehmenFuer.value = { ...frische, dublette: emailDublette(frische) }
    }
  } finally {
    aufnehmenLaeuft.value = false
    processing.value[id] = false
  }
}

// ── Ablehnen (OP-UI-13) ───────────────────────────────────────────────────

const ablehnenFuer = ref(null)
const ablehnGrund = ref('')
const ablehnenFehler = ref('')
const ablehnenLaeuft = ref(false)
const ablehnenSchutz = useFormularSchutz(() => ablehnGrund.value, () => ablehnenLaeuft.value)
async function ablehnenSchliessen() {
  if (await ablehnenSchutz.darfSchliessen()) ablehnenFuer.value = null
}

function ablehnen(a) {
  ablehnGrund.value = ''
  ablehnenFehler.value = ''
  ablehnenSchutz.merken()
  ablehnenFuer.value = { ...a }
}

async function ablehnenBestaetigen() {
  const ziel = ablehnenFuer.value
  if (!ziel || ablehnenLaeuft.value) return
  const id = ziel.name
  const grund = ablehnGrund.value
  ablehnenFehler.value = ''
  ablehnenLaeuft.value = true
  processing.value[id] = true
  try {
    const res = await apiCall('diakronos.diakonos.api.admin_hub.lehne_anmeldung_ab', { anmeldung_id: id, grund })
    if (!res.success) throw new Error('Die Anfrage konnte nicht abgelehnt werden. Bitte erneut versuchen.')
    if (res.success) {
      ablehnenFuer.value = null
      ablehnenSchutz.merken()
      showToast('Anfrage abgelehnt')
      await fetchData()
    }
  } catch (err) {
    ablehnenFehler.value = err?.message || 'Ablehnen nicht möglich.'
  } finally {
    ablehnenLaeuft.value = false
    processing.value[id] = false
  }
}

// ── Links ─────────────────────────────────────────────────────────────────

const showCreateLink = ref(false)
/** M-1: die unter „Einstellungen → Registrierung“ gepflegten Vorgaben. */
const linkVorgaben = ref({ laufzeitTage: 30, maxAnmeldungen: 0 })
const leererLink = () => {
  // M-1: neue Links werden mit den Gemeinde-Vorgaben vorbelegt, damit der
  // Hinweis im Einstellungsbereich stimmt. Der Server wendet dieselben
  // Vorgaben an, wenn hier nichts eingetragen wird.
  const v = linkVorgaben.value
  const gueltig = v.laufzeitTage > 0
    ? new Date(Date.now() + v.laufzeitTage * 86400000).toISOString().slice(0, 10)
    : ''
  return {
    bezeichnung: '', typ: 'Mitglied-Registrierung',
    gueltig_bis: gueltig, max_anmeldungen: v.maxAnmeldungen || 0, anmeldeformular_id: '',
    // M-1 (R-N9b): ausdruecklich unbefristet/unbegrenzt, unabhaengig von der
    // Gemeinde-Vorgabe. Leer heisst weiter Vorgabe (Server wendet sie an).
    ohne_ablauf: false, unbegrenzt: false,
  }
}
const newLink = ref(leererLink())
const linkSpeichert = ref(false)
const linkFehler = ref({})
const linkSchutz = useFormularSchutz(() => newLink.value, () => linkSpeichert.value)
function linkOeffnen() {
  newLink.value = leererLink()
  linkFehler.value = {}
  linkSchutz.merken()
  showCreateLink.value = true
}

/** M-1: Link-Vorgaben der Gemeinde laden (nur Admin; Fehler bleiben still). */
async function ladeLinkVorgaben() {
  try {
    const res = await apiCall('diakronos.diakonos.api.gemeinde.gemeinde_get_einstellungen', {})
    const d = res.message || res
    linkVorgaben.value = {
      laufzeitTage: Number(d.link_laufzeit_tage ?? 30),
      maxAnmeldungen: Number(d.link_max_anmeldungen ?? 0),
    }
  } catch {
    // Ohne Vorgaben bleibt der Standard (30 Tage, unbegrenzt) — kein Fehler.
  }
}
async function linkSchliessen() {
  if (await linkSchutz.darfSchliessen()) showCreateLink.value = false
}
function fehlerFokussieren(formularId) {
  requestAnimationFrame(() => document.getElementById(formularId)?.querySelector('[aria-invalid="true"]')?.focus())
}

/**
 * N3 — Zustand einer Linkkarte.
 *
 * Der Server entscheidet den Zustand (`zustand` aus `admin_hub`); hier wird er
 * nur in Farbe und Wort übersetzt. Fehlt das Feld (ältere Antwort), fällt die
 * Anzeige auf den rohen `aktiv`-Wert zurück — nie auf einen geratenen Zustand.
 */
function istAus(l) {
  return l.zustand === 'abgelaufen' || l.zustand === 'voll' || l.zustand === 'inaktiv'
    || (l.zustand === undefined && !l.aktiv)
}

function zustandText(l) {
  switch (l.zustand) {
    case 'abgelaufen': return 'Abgelaufen'
    case 'voll':       return 'Voll'
    case 'inaktiv':    return 'inaktiv'
    case 'aktiv':      return 'aktiv'
    default:           return l.aktiv ? 'aktiv' : 'inaktiv'
  }
}

function zustandVariante(l) {
  switch (l.zustand) {
    case 'abgelaufen': return 'err'
    case 'voll':       return 'warn'
    case 'inaktiv':    return 'neutral'
    case 'aktiv':      return 'ok'
    default:           return l.aktiv ? 'ok' : 'neutral'
  }
}

/** Typ kurz und ohne Bindestrich-Fachsprache (S15). */
function typKurz(typ) {
  return typ === 'Gast-Anmeldung' ? 'Gast' : 'Registrierung'
}

function istGastLink(l) {
  return l.typ === 'Gast-Anmeldung'
}

/** Balkenbreite der Plätze (maximal 100 %). */
function balkenBreite(l) {
  const gesamt = Number(l.plaetze_gesamt) || 0
  if (gesamt <= 0) return '0%'
  const anteil = Math.min(100, Math.round((Number(l.plaetze_belegt) || 0) / gesamt * 100))
  return anteil + '%'
}

// ── Verlängern (N3) ───────────────────────────────────────────────────────

const verlaengernFuer = ref(null)
const verlaengernDatum = ref('')
const verlaengernMax = ref(0)
const verlaengernLaeuft = ref(false)
const verlaengernFehler = ref('')
const verlaengernSchutz = useFormularSchutz(
  () => [verlaengernDatum.value, verlaengernMax.value], () => verlaengernLaeuft.value,
)
async function verlaengernSchliessen() {
  if (await verlaengernSchutz.darfSchliessen()) verlaengernFuer.value = null
}

const verlaengernTitel = computed(() => {
  const l = verlaengernFuer.value
  return l ? `„${l.bezeichnung}“ verlängern` : 'Link verlängern'
})

function verlaengernOeffnen(l) {
  verlaengernDatum.value = l.gueltig_bis ? String(l.gueltig_bis).slice(0, 10) : ''
  verlaengernMax.value = Number(l.plaetze_gesamt) || 0
  verlaengernFehler.value = ''
  verlaengernSchutz.merken()
  // R-N3-main-commits (wichtig 2): „Verlängern“ schaltet den Link wieder ein —
  // das Fenster muss es bei einem ausgeschalteten Link sagen.
  verlaengernFuer.value = { ...l, inaktiv: l.zustand === 'inaktiv' }
}

async function verlaengernBestaetigen() {
  const l = verlaengernFuer.value
  if (!l || verlaengernLaeuft.value) return
  verlaengernFehler.value = ''
  const plaetze = Number(verlaengernMax.value)
  if (!Number.isSafeInteger(plaetze) || plaetze < 0) {
    verlaengernFehler.value = 'Bitte gib für die Plätze eine ganze Zahl ab 0 ein (0 = unbegrenzt).'
    fehlerFokussieren('reg-verlaengern-form')
    return
  }
  verlaengernLaeuft.value = true
  try {
    const res = await apiCall('diakronos.diakonos.api.registrierungslink_api.verlaengern_link', {
      link_id: l.name,
      gueltig_bis: verlaengernDatum.value || '',
      max_anmeldungen: plaetze,
    })
    if (!res.success) throw new Error('Der Link konnte nicht verlängert werden. Bitte erneut versuchen.')
    if (res.success) {
      verlaengernFuer.value = null
      verlaengernSchutz.merken()
      showToast('Link verlängert')
      await fetchData()
      if (res.link?.anfragen_offen > 0) {
        showToast(`${res.link.anfragen_offen} offene ${res.link.anfragen_offen === 1 ? 'Anfrage wartet' : 'Anfragen warten'} auf Prüfung`, 'info')
      }
    }
  } catch (err) {
    verlaengernFehler.value = err?.message || 'Der Link konnte nicht verlängert werden.'
  } finally {
    verlaengernLaeuft.value = false
  }
}

async function createLink() {
  if (linkSpeichert.value) return
  linkFehler.value = pflichtFehler([
    ['bezeichnung', newLink.value.bezeichnung, 'eine Bezeichnung'],
    ['typ', newLink.value.typ, 'einen Typ'],
  ])
  if (Object.keys(linkFehler.value).length) { fehlerFokussieren('reg-link-form'); return }
  linkSpeichert.value = true
  try {
    // M-1: ausdrueckliche Wahl ueberschreibt die Vorbelegung — sonst schickt
    // der Client die Vorgabe-Zahl als "ausdruecklich" mit.
    const nutzlast = { ...newLink.value }
    if (nutzlast.ohne_ablauf) nutzlast.gueltig_bis = ''
    if (nutzlast.unbegrenzt) nutzlast.max_anmeldungen = 0
    const res = await apiCall('diakronos.diakonos.api.registrierungslink_api.create_link', nutzlast)
    if (res.success) {
      showToast('Link erstellt')
      showCreateLink.value = false
      newLink.value = leererLink()
      linkSchutz.merken()
      await fetchData()
    }
  } catch (err) {
    linkFehler.value = { speichern: err?.message || 'Der Link konnte nicht erstellt werden. Bitte erneut versuchen.' }
  } finally {
    linkSpeichert.value = false
  }
}

async function toggleLink(l) {
  try {
    const res = await apiCall('diakronos.diakonos.api.registrierungslink_api.toggle_link', { link_id: l.name })
    if (res.success) {
      l.aktiv = res.aktiv ? 1 : 0
      showToast(l.aktiv ? 'Link aktiviert' : 'Link deaktiviert')
    }
  } catch (err) {
    showToast(err?.message || 'Fehler', 'error')
  }
}

async function deleteLink(l) {
  // N3: das Löschen fragt im App-Fenster nach (OP-UI-16 / S4.2) und nennt die
  // Folgen in Zahlen — kein natives confirm().
  const anzahl = Number(l.anmeldungen_count) || 0
  const folgen = anzahl > 0
    ? `Dabei werden ${anzahl} ${anzahl === 1 ? 'Anmeldung' : 'Anmeldungen'} dieses Links entfernt.`
    : 'Es hängen keine Anmeldungen daran.'
  if (!await bestaetigen(`„${l.bezeichnung}“ löschen?`, `${folgen} Das lässt sich nicht rückgängig machen.`)) return
  try {
    const res = await apiCall('diakronos.diakonos.api.registrierungslink_api.delete_link', { link_id: l.name })
    if (res.success) {
      showToast('Link gelöscht')
      await fetchData()
    }
  } catch (err) {
    showToast(err?.message || 'Fehler', 'error')
  }
}

// ── Formulare ─────────────────────────────────────────────────────────────

const showCreateFormular = ref(false)
const leeresFormular = () => ({ bezeichnung: '', mit_gaesten: false, mit_kinder: false })
const newFormular = ref(leeresFormular())
const formularFelder = ref([])
const formularSpeichert = ref(false)
const formularFehler = ref({})
// OP-ADMIN-19: `null` = neues Formular; sonst der `name` des Formulars, das
// gerade bearbeitet wird. Ohne diesen Wert gab es keinen Weg, ein bestehendes
// Formular zu öffnen oder zu ändern.
const formularBearbeitet = ref(null)
const formularSchutz = useFormularSchutz(
  () => [newFormular.value, formularFelder.value], () => formularSpeichert.value,
)
function formularOeffnen() {
  newFormular.value = leeresFormular()
  formularFelder.value = []
  formularFehler.value = {}
  formularBearbeitet.value = null
  formularSchutz.merken()
  showCreateFormular.value = true
}

/** OP-ADMIN-19: Ein Formular oeffnen, um es zu aendern.
 *  Die Felder kommen vom Server (`get_anmeldeformular_felder`) — vorher gab
 *  es diesen Weg gar nicht, ein Formular war damit nicht aenderbar. */
async function formularBearbeiten(f) {
  formularFehler.value = {}
  try {
    const antwort = await apiCall('diakronos.diakonos.api.admin_hub.get_anmeldeformular_felder', {
      formular_id: f.name,
    })
    const daten = antwort?.message ?? antwort
    formularBearbeitet.value = f.name
    newFormular.value = {
      bezeichnung: daten?.bezeichnung || f.bezeichnung || '',
      mit_gaesten: !!daten?.mit_gaesten,
      mit_kinder: !!daten?.mit_kinder,
    }
    formularFelder.value = (Array.isArray(daten?.felder) ? daten.felder : []).map(z => ({
      label: z.label || '',
      feldtyp: z.feldtyp || 'Text',
      optionen: z.optionen || '',
      pflichtfeld: !!z.pflichtfeld,
      fuer_gaeste: !!z.fuer_gaeste,
      fuer_kinder: !!z.fuer_kinder,
    }))
    formularSchutz.merken()
    showCreateFormular.value = true
  } catch (err) {
    showToast(formularMeldung(err, 'Das Formular konnte nicht geladen werden.'), 'error')
  }
}

/** OP-ADMIN-19: Formular loeschen — mit Rueckfrage im App-Fenster.
 *  Der Server verweigert es, solange ein Registrierungslink darauf zeigt. */
async function formularEntfernen(f) {
  const ok = await bestaetigen(
    `Formular „${f.bezeichnung}“ löschen?`,
    'Das Anmeldeformular wird entfernt. Das geht nur, wenn kein Registrierungslink mehr darauf verweist.',
  )
  if (!ok) return
  try {
    await apiCall('diakronos.diakonos.api.admin_hub.delete_anmeldeformular', {
      formular_id: f.name, bestaetigt: 1,
    })
    showToast('Formular gelöscht')
    await fetchData()
  } catch (err) {
    showToast(formularMeldung(err, 'Das Formular konnte nicht gelöscht werden.'), 'error')
  }
}

/** Fehlertext einer Formular-Anfrage (verstaendlich). */
function formularMeldung(err, fallback) {
  const text = String(err?.message || '').trim()
  if (!text || /^HTTP \d+$/.test(text)) return fallback
  return text
}
async function formularSchliessen() {
  if (await formularSchutz.darfSchliessen()) {
    showCreateFormular.value = false
    formularBearbeitet.value = null
  }
}

function addFeld() {
  formularFelder.value.push({ label: '', feldtyp: 'Text', pflichtfeld: false, fuer_gaeste: false, fuer_kinder: false })
}

async function createFormular() {
  if (formularSpeichert.value) return
  formularFehler.value = pflichtFehler([
    ['bezeichnung', newFormular.value.bezeichnung, 'eine Bezeichnung'],
    ...formularFelder.value.map((f, i) => ['reg-feld-' + i, f.label, 'eine Feldbezeichnung']),
  ])
  if (Object.keys(formularFehler.value).length) { fehlerFokussieren('reg-formular-form'); return }
  formularSpeichert.value = true
  try {
    const cleanFelder = formularFelder.value.map(f => ({
      label: f.label,
      feldtyp: f.feldtyp,
      optionen: f.optionen || '',
      pflichtfeld: f.pflichtfeld ? 1 : 0,
      fuer_gaeste: f.fuer_gaeste ? 1 : 0,
      fuer_kinder: f.fuer_kinder ? 1 : 0,
    }))
    if (formularBearbeitet.value) {
      // OP-ADMIN-19: aendern — Kopf und Felder in EINEM Aufruf, damit ein
      // halb gespeichertes Formular nicht entstehen kann.
      await apiCall('diakronos.diakonos.api.admin_hub.update_anmeldeformular', {
        formular_id: formularBearbeitet.value,
        bezeichnung: newFormular.value.bezeichnung,
        mit_gaesten: newFormular.value.mit_gaesten ? 1 : 0,
        mit_kinder: newFormular.value.mit_kinder ? 1 : 0,
        felder_json: JSON.stringify(cleanFelder),
      })
      showToast('Formular gespeichert')
    } else {
      const res = await apiCall('diakronos.diakonos.api.admin_hub.create_anmeldeformular', {
        bezeichnung: newFormular.value.bezeichnung,
        mit_gaesten: newFormular.value.mit_gaesten ? 1 : 0,
        mit_kinder: newFormular.value.mit_kinder ? 1 : 0,
      })
      if (res.success) {
        if (cleanFelder.length > 0) {
          await apiCall('diakronos.diakonos.api.admin_hub.update_anmeldeformular_felder', {
            formular_id: res.id,
            felder_json: JSON.stringify(cleanFelder),
          })
        }
        showToast('Formular erstellt')
      }
    }
    showCreateFormular.value = false
    newFormular.value = leeresFormular()
    formularFelder.value = []
    formularBearbeitet.value = null
    formularSchutz.merken()
    await fetchData()
  } catch (err) {
    formularFehler.value = { speichern: formularMeldung(err, 'Das Formular konnte nicht gespeichert werden. Bitte erneut versuchen.') }
  } finally {
    formularSpeichert.value = false
  }
}

// ── Details ───────────────────────────────────────────────────────────────

const detailAnmeldung = ref(null)
function showDetail(a) { detailAnmeldung.value = a }

/** OP-ADMIN-8: Titel des Detailfensters = „Anfrage von Vorname Nachname“
 *  statt der rohen ID. Nach `detailAnmeldung` definiert (sonst TDZ-Fehler). */
const detailName = computed(() => {
  const a = detailAnmeldung.value
  if (!a) return ''
  const name = `${a.vorname || ''} ${a.nachname || ''}`.trim()
  return name || (a.email || a.name || '')
})

function copyLink(url) {
  // UXD-R3: der Server liefert die Adresse als `/diakonos/…?token=…` (Altdaten
  // trugen sogar nur `/registrierung?token=…`). Kopiert werden muss eine
  // VOLLSTAENDIGE Adresse, sonst landet der Empfaenger im Nichts.
  const text = url ? new URL(url, window.location.origin).href : ''
  if (!text) {
    showToast('Kein Link vorhanden', 'error')
    return
  }
  navigator.clipboard.writeText(text).then(() => showToast('Link kopiert'))
}

function formatDate(dateStr) {
  if (!dateStr) return '–'
  const d = new Date(dateStr)
  if (isNaN(d)) return dateStr
  return d.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric' })
}

/** Anfragestatus → Kennzeichen-Variante. */
function statusVariante(status) {
  const map = {
    'Bestätigt': 'ok',
    'Ausstehend': 'warn',
    'Anmeldeanfrage': 'warn',
    'Abgelehnt': 'err',
    'Warteliste': 'info',
  }
  return map[status] || 'neutral'
}

// Symbole (dekorativ)
const IconPlus  = () => h('svg', { width:14, height:14, viewBox:'0 0 24 24', fill:'none', stroke:'currentColor', 'stroke-width':2, 'stroke-linecap':'round', 'stroke-linejoin':'round' }, [h('line',{x1:12,y1:5,x2:12,y2:19}), h('line',{x1:5,y1:12,x2:19,y2:12})])
const IconCheck = () => h('svg', { width:14, height:14, viewBox:'0 0 24 24', fill:'none', stroke:'currentColor', 'stroke-width':2, 'stroke-linecap':'round', 'stroke-linejoin':'round' }, [h('polyline',{points:'20 6 9 17 4 12'})])
const IconX     = () => h('svg', { width:14, height:14, viewBox:'0 0 24 24', fill:'none', stroke:'currentColor', 'stroke-width':2, 'stroke-linecap':'round', 'stroke-linejoin':'round' }, [h('line',{x1:18,y1:6,x2:6,y2:18}), h('line',{x1:6,y1:6,x2:18,y2:18})])
const IconLink  = () => h('svg', { width:12, height:12, viewBox:'0 0 24 24', fill:'none', stroke:'currentColor', 'stroke-width':2, 'stroke-linecap':'round', 'stroke-linejoin':'round' }, [h('path',{d:'M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71'}), h('path',{d:'M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71'})])
// N3: Verlängern (Ablauf/Plätze) und Löschen im Konfliktfenster.
const IconRefresh = () => h('svg', { width:14, height:14, viewBox:'0 0 24 24', fill:'none', stroke:'currentColor', 'stroke-width':2, 'stroke-linecap':'round', 'stroke-linejoin':'round' }, [h('polyline',{points:'23 4 23 10 17 10'}), h('polyline',{points:'1 20 1 14 7 14'}), h('path',{d:'M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15'})])
const IconTrash = () => h('svg', { width:14, height:14, viewBox:'0 0 24 24', fill:'none', stroke:'currentColor', 'stroke-width':2, 'stroke-linecap':'round', 'stroke-linejoin':'round' }, [h('polyline',{points:'3 6 5 6 21 6'}), h('path',{d:'M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6'}), h('path',{d:'M10 11v6M14 11v6'}), h('path',{d:'M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2'})])

onMounted(() => { fetchData(); ladeLinkVorgaben() })
</script>

<style scoped>
.reg-bereich { margin-bottom: var(--sp-5); }

.reg-aktion { display: flex; margin-bottom: var(--sp-5); }

/* OP-UI-19: Die eigene Ladeform (reg-skelett) ist durch DkSkelett ersetzt. */

.reg-jetzt { white-space: nowrap; }
.reg-muted { color: var(--muted); }
.reg-aktionen { display: flex; gap: 6px; flex-wrap: wrap; }

.reg-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: var(--sp-4); }
/* N3: abgelaufene/volle/ausgeschaltete Links treten zurück (Konzept: „Karte grau“). */
.reg-karte-grau { opacity: .75; }
.reg-link-titel { font-size: var(--fs-h3); font-weight: var(--fw-h); color: var(--text); margin: 0; }
.reg-link-meta { display: flex; gap: var(--sp-3); font-size: var(--fs-sm); color: var(--muted); margin-bottom: var(--sp-2); }
.reg-link-hinweis { font-size: var(--fs-sm); color: var(--muted); margin: 0 0 var(--sp-2); }
.reg-link-plaetze { font-size: var(--fs-sm); color: var(--text); margin: var(--sp-3) 0 var(--sp-1); }
/* Balken der belegten Plätze (Konzept Abschnitt 5: „x von y Plätzen“ mit Balken). */
.reg-balken { height: 6px; background: var(--surface-2); border-radius: 999px; overflow: hidden; margin-bottom: var(--sp-2); }
.reg-balken-fuell { height: 100%; background: var(--primary); border-radius: 999px; transition: width .2s var(--ease); }
.reg-link-ablauf { font-size: var(--fs-sm); color: var(--err); margin-bottom: var(--sp-2); }
.reg-link-aktionen { display: flex; gap: var(--sp-2); flex-wrap: wrap; }

.reg-eingaben { border: 0; margin: 0; padding: 0; min-width: 0; }
.reg-schalter { display: flex; align-items: flex-start; gap: var(--sp-2); font-size: var(--fs-sm); }
.reg-schalter input { margin-top: var(--sp-1); flex-shrink: 0; }
.reg-formular { display: flex; flex-direction: column; gap: var(--sp-3); }
.reg-kaestchen { display: flex; gap: var(--sp-4); flex-wrap: wrap; }
.reg-feldbau { margin-top: var(--sp-3); }
.reg-feldbau-kopf { display: flex; justify-content: space-between; align-items: center; margin-bottom: var(--sp-3); }
.reg-feldbau-titel { font-size: var(--fs-sm); font-weight: 600; color: var(--text); }
.reg-feldzeile { display: grid; grid-template-columns: 1fr 120px 80px 40px; gap: var(--sp-2); align-items: center; margin-bottom: var(--sp-2); }
@media (max-width: 520px) { .reg-feldzeile { grid-template-columns: 1fr; } }

.reg-detail { display: flex; flex-direction: column; gap: var(--sp-3); }
.reg-dialog-text { margin: 0 0 var(--sp-3); color: var(--text); line-height: 1.5; }
.reg-detail-grid { display: grid; gap: var(--sp-3); font-size: var(--fs); }
.reg-detail-grid div { color: var(--text); }
.reg-detail-abschnitt { margin: var(--sp-4) 0; }
.reg-detail-abschnitt h4 { font-size: var(--fs-h4); font-weight: var(--fw-h); margin: 0 0 var(--sp-2); color: var(--text); }
.reg-antworten { display: grid; grid-template-columns: auto 1fr; gap: 6px var(--sp-4); font-size: var(--fs-sm); }
.reg-antworten dt { color: var(--muted); }
.reg-antworten dd { color: var(--text); margin: 0; }
.reg-kinder { list-style: none; padding: 0; margin: 0; font-size: var(--fs-sm); }
.reg-kinder li { padding: var(--sp-1) 0; border-bottom: 1px solid var(--divider); }
.reg-kinder-geb { color: var(--muted); }

</style>
