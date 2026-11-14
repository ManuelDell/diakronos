<template>
  <div :class="[{ 'dk-screen dk-screen-enter': !eingebettet }, { 'reg-screen--dialog': showCreateFormular }]">
    <!-- UX3j (Entwurf A3, Punkt 3): Die Reiterzeile von „Personen“ steht in
         JEDEM Reiter oben (Rahmen pages/Personen.vue). Steht diese Seite
         allein (embedded = false), trägt sie einen eigenen Kopf.
         Die Hauptaktion des SICHTBAREN Unterbereichs liegt hier im Kopf —
         genau EIN gefüllter Knopf je Ansicht: Links „Neuer Link“,
         Formulare „Neues Formular“. Der Unterbereich „Anfragen“ hat keine
         Anlege-Aktion (seine Arbeit ist das Aufnehmen, je Zeile) — dort ist
         „Person anlegen“ der eine Primärknopf. -->
    <DkPageHeader v-if="!embedded" title="Anfragen" sub="Anfragen, Links & Formulare verwalten">
      <template #actions>
        <DkButton v-if="unterbereich === 'links'" variant="primary" @click="linkOeffnen">
          <IconPlus /> Neuer Link
        </DkButton>
        <DkButton v-else-if="unterbereich === 'formulare'" variant="primary" @click="formularOeffnen">
          <IconPlus /> Neues Formular
        </DkButton>
      </template>
    </DkPageHeader>

    <!-- N2 (Konzept Abschnitt 3, Reiter 3 „Anfragen“): der Zustand der
         Anfragen (Offen/Aufgenommen/Abgelehnt). Der Begriff „Anmeldung“
         bleibt dem Login vorbehalten.
         UX3j: Der Unterbereich kommt über die Eigenschaft `unterbereich`
         herein und steht in der ADRESSE (#/personen/anfragen[/<unter>],
         menue.js `personenAnfragenReiter`): Die zweite, kleinere Reiterzeile
         zeichnet der Rahmen — diese Seite bringt KEINEN eigenen Umschalter
         mehr mit (zwei Reiterzeilen für dieselbe Wahl waren der Befund).
         UX-A2b (Entwurf A2, Befunde DMB-09a956e8457d + DMB-d4f788c04158):
         Die Status-Reiter „Offen · Aufgenommen · Abgelehnt“ standen ÜBER den
         Unterbereichen und filterten deshalb auch dann, wenn man bei „Links“
         oder „Formularen“ war — dort ohne jede Wirkung. Jetzt steht der
         Statusfilter DIREKT über der Anfragen-Tabelle, also nur dort, wo er
         wirkt. UX3j-Nacharbeit: DERSELBE Baustein wie Liste und Datenschutz
         (DkSegment) mit derselben Zähler-Schreibweise — unter „Personen“ gibt
         es nur noch EIN Filter-Aussehen. -->

    <!-- Unterbereich 1: Anfragen -->
    <div v-if="unterbereich === 'anfragen'">
      <!-- UX-A2b + UX3j (Nacharbeit Punkt 1): Statusfilter MIT Zahlen, direkt
           über der Tabelle. Nur hier — bei Links und Formularen gibt es keinen
           Statusfilter. „Offen“ ist die Arbeitsliste und deshalb der
           Ruhezustand; „Alle“ zeigt auch Warteliste-Anfragen. Derselbe
           Baustein und dieselbe Zähler-Schreibweise wie Liste und Datenschutz
           (DkSegment) — EIN Filter-Aussehen unter „Personen“. -->
      <DkSegment
        v-if="!loading"
        class="reg-statusfilter"
        :model-value="statusFilter"
        :options="statusFilterOptionen"
        aria-label="Anfragen nach Status filtern"
        @update:model-value="statusFilter = $event"
      />

      <!-- OP-UI-19: gemeinsames Ladeskelett statt einer eigenen Form. -->
      <DkSkelett v-if="loadingSkelett" form="tabelle" :anzahl="5" text="Anfragen werden geladen …" />

      <DkCard v-else flach>
        <DkTable
          :spalten="anmeldungSpalten"
          :leer="filteredAnmeldungen.length === 0"
          :leer-titel="leerText"
        >
          <tr v-for="a in filteredAnmeldungen" :key="a.name">
            <td class="reg-jetzt">{{ formatDate(a.anmeldedatum) }}</td>
            <td>{{ a.vorname }} {{ a.nachname }}</td>
            <td>{{ artText(a.anmeldungstyp) }}</td>
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
            <td>
              <!-- UX-A2b: dieselbe Sprache wie die Filterchips (Offen ·
                   Aufgenommen · Abgelehnt) statt der rohen Server-Werte
                   „Anmeldeanfrage / Ausstehend / Bestätigt“. -->
              <DkBadge :variant="statusSprache(a.status).variant">{{ statusSprache(a.status).wort }}</DkBadge>
            </td>
            <!-- FIX-4: Aktionszelle mit `.is-aktion` — DkTable hält sie in
                 ihrer Spalte (Umbruch statt Überlagerung). Der Wrapper
                 `.reg-aktionen` hält die Knöpfe als Flex-Zeile mit
                 Token-Abstand (Punkt 3 der Review-Auflage). -->
            <td class="is-aktion">
              <!-- UX1f (S1): Die Hauptaktion einer offenen Anfrage ist das
                   Aufnehmen; sie ist der gefüllte Knopf. „Ablehnen“ ist die
                   Gegenentscheidung und steht als secondary daneben — der
                   Warnhinweis im Dialog trägt die Folge, nicht die Farbe.
                   Beide in voller Höhe (--control-h), Reihenfolge unverändert. -->
              <div class="reg-aktionen">
                <DkButton v-if="istOffen(a)"
                  variant="primary" :disabled="processing[a.name]" @click="aufnehmen(a)">
                  <IconCheck /> Aufnehmen
                </DkButton>
                <DkButton v-if="istOffen(a)"
                  variant="secondary" :disabled="processing[a.name]" @click="ablehnen(a)">
                  <IconX /> Ablehnen
                </DkButton>
                <DkButton variant="secondary" size="md" @click="showDetail(a)">Details</DkButton>
              </div>
            </td>
          </tr>
        </DkTable>
      </DkCard>
    </div>

    <!-- Unterbereich 2: Links & QR-Codes (N3: voller Link, Oeffnen, QR) -->
    <div v-if="unterbereich === 'links'">
      <DkSkelett v-if="loadingLinksSkelett" form="karten" :anzahl="3" text="Links werden geladen …" />

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

          <!-- N3: Gültigkeit und Plätze sichtbar (Konzept Abschnitt 5).
               REG-1b: „Gültig ab“ steht neben „Gültig bis“ — vor diesem Tag
               ist der Link für Besucher noch nicht nutzbar. -->
          <div v-if="l.gueltig_ab || l.gueltig_bis" class="reg-link-zeitraum">
            <span v-if="l.gueltig_ab">Gültig ab: {{ formatDate(l.gueltig_ab) }}</span>
            <span v-if="l.gueltig_ab && l.gueltig_bis" class="reg-muted">·</span>
            <span v-if="l.gueltig_bis">Gültig bis: {{ formatDate(l.gueltig_bis) }}</span>
          </div>
          <div v-else class="reg-link-meta">Ohne Ablaufdatum</div>

          <div v-if="l.gueltig_ab && l.zustand === 'bevorstehend'" class="reg-link-meta">
            <span>Startet am {{ formatDate(l.gueltig_ab) }} — bis dahin sehen Besucher nur einen Hinweis.</span>
          </div>

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
            <!-- UX1f (S1): „Verlängern“ ist die Arbeit eines abgelaufenen
                 Links; „Pausieren/Aktivieren“ und „Löschen“ stehen daneben in
                 voller Höhe.
                 UX1h (S1): Der gefüllte Knopf wird innerhalb der Ansicht
                 gedreht — die Liste der Links hat genau einen Primärknopf
                 („Neuer Link“ oben), ein zweiter je abgelaufener Zeile wäre
                 eine zweite Hauptaktion auf derselben Fläche. Die Zeile sagt
                 ihre Rangfolge über Reihenfolge und Schrift („Löschen“ trägt
                 die Gefahrenfarbe als Text). -->
            <DkButton v-if="istAus(l)" variant="secondary" @click="verlaengernOeffnen(l)">
              <IconRefresh /> Verlängern
            </DkButton>
            <DkButton variant="secondary" @click="toggleLink(l)">
              {{ l.aktiv ? 'Pausieren' : 'Aktivieren' }}
            </DkButton>
            <DkButton variant="secondary" class="reg-loeschen-schrift" @click="deleteLink(l)">Löschen</DkButton>
          </div>
        </DkCard>
      </div>
    </div>

    <!-- Unterbereich 3: Formulare -->
    <div v-if="unterbereich === 'formulare'">
      <DkSkelett v-if="loadingFormulareSkelett" form="karten" :anzahl="3" text="Formulare werden geladen …" />

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
            <!-- UX1f (S1): „Bearbeiten“ ist die Arbeit dieser Zeile;
                 „Löschen“ (dauerhaft) steht daneben, die Gefahr trägt die
                 Schriftfarbe.
                 UX1h (S1): Der gefüllte Knopf der Ansicht ist „Neues
                 Formular“ oben — ein gefüllter Knopf je Tabellenzeile wäre
                 eine zweite Hauptaktion auf derselben Fläche. -->
            <td class="is-aktion">
              <DkButton variant="secondary" @click="formularBearbeiten(f)">Bearbeiten</DkButton>
              <DkButton variant="secondary" class="reg-loeschen-schrift" @click="formularEntfernen(f)">Löschen</DkButton>
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
        <DkField v-slot="feld" label="Bezeichnung" required :error="linkFehler.bezeichnung"
          :wert="newLink.bezeichnung" @update:wert="newLink.bezeichnung = $event">
          <input v-bind="feld.feldProps"
            required class="dk-ui-eingabe" placeholder="z. B. Gemeindefest 2026" />
        </DkField>
        <!-- UX3h5: DkSelect nimmt `modelValue`; der Wert läuft über `v-model`,
             die leere Auswahl als `emptyValue`. Kennungen, Pflicht und
             Fehlerzustand kommen aus dem Feld-Slot. -->
        <DkField v-slot="feld" label="Typ" required :error="linkFehler.typ">
          <DkSelect :id="feld.id" :aria-describedby="feld['aria-describedby']"
            required :aria-invalid="feld['aria-invalid'] ? 'true' : undefined"
            v-model="newLink.typ" :options="linkTypOptionen" empty-value="" />
        </DkField>
        <!-- REG-1b: Start und Ende eines Links gehoeren zusammen — sie stehen
             deshalb nebeneinander (Zeitraum in Leserichtung). Am Handy bricht
             die Reihe um (`.reg-zeitraum`). -->
        <div class="reg-zeitraum">
          <DkField label="Gültig ab" help="Leer = sofort nutzbar.">
            <input v-model="newLink.gueltig_ab" type="date" class="dk-ui-eingabe" />
          </DkField>
          <DkField label="Gültig bis" :help="ohneAblaufHinweis">
            <input v-model="newLink.gueltig_bis" type="date" class="dk-ui-eingabe"
              :disabled="newLink.ohne_ablauf" />
          </DkField>
        </div>
        <!-- UI-R10b: die Laufzeit-Vorgabe wird NIE im Frontend gerechnet. Sie
             kommt aus `registrierungslink_api.get_link_vorgaben`; fehlt sie,
             sagt der Satz das ausdrücklich (das Feld bleibt dann leer). -->
        <DkHint v-if="!newLink.ohne_ablauf" variant="info" data-test="reg-laufzeit-hinweis">
          {{ laufzeitHinweis }}
        </DkHint>
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
        <!-- UX3h5: Auswahlfeld wie alle übrigen (DkSelect) — Kennungen fürs
             Label aus dem Feld-Slot, der Wert über `v-model`, die leere Auswahl
             als `emptyValue`. -->
        <DkField v-slot="feld" label="Anmeldeformular">
          <DkSelect :id="feld.id" :aria-describedby="feld['aria-describedby']"
            v-model="newLink.anmeldeformular_id" :options="formularOptionen" empty-value="" />
        </DkField>
       </fieldset>
      </form>
      <template #footer>
        <DkButton variant="secondary" :disabled="linkSpeichert" @click="linkSchliessen">Abbrechen</DkButton>
        <DkButton variant="primary" type="submit" form="reg-link-form" :loading="linkSpeichert">Anlegen</DkButton>
      </template>
    </DkDialog>

    <!-- Dialog: Formular erstellen / bearbeiten (OP-ADMIN-19) -->
    <DkDialog v-model="showCreateFormular" :before-close="formularSchutz.darfSchliessen"
              :title="formularBearbeitet ? 'Anmeldeformular bearbeiten' : 'Neues Anmeldeformular'">
      <form id="reg-formular-form" novalidate @submit.prevent="createFormular">
       <fieldset class="reg-formular reg-eingaben" :disabled="formularSpeichert">
        <DkHint v-if="formularFehler.speichern" variant="err">{{ formularFehler.speichern }}</DkHint>
        <DkField v-slot="feld" label="Bezeichnung" required :error="formularFehler.bezeichnung"
          :wert="newFormular.bezeichnung" @update:wert="newFormular.bezeichnung = $event">
          <input v-bind="feld.feldProps"
            required class="dk-ui-eingabe" placeholder="z. B. Standard-Anmeldung" />
        </DkField>
        <div class="reg-kaestchen">
          <DkCheckbox v-model="newFormular.mit_gaesten" label="Mit Gästen" />
          <DkCheckbox v-model="newFormular.mit_kinder" label="Mit Kinder-Option" />
        </div>

        <!-- REG-1b: Beschreibung — reiner Text, erscheint über dem Formular. -->
        <DkField label="Beschreibung"
                 help="Erscheint über dem Formular. Absätze und Zeilenumbrüche bleiben erhalten.">
          <textarea v-model="newFormular.beschreibung" class="dk-ui-eingabe" rows="4"
                    maxlength="5000" data-test="reg-formular-beschreibung"
                    placeholder="z. B. Herzlich willkommen! Melde dich hier für die Gemeinde an." />
        </DkField>

        <!-- REG-1b: Banner und Hintergrundbild. Banner steht über dem Kopf,
             Hintergrund liegt gedämpft hinter der Karte. -->
        <div class="reg-bilder">
          <div v-for="bild in bildFelder" :key="bild.rolle" class="reg-bild">
            <span class="reg-bild-titel">{{ bild.titel }}</span>
            <img v-if="bild.url" :src="bild.url" alt="" class="reg-bild-vorschau" />
            <div class="reg-bild-aktionen">
              <input :ref="el => (bildEingabe[bild.rolle] = el)" type="file"
                     accept="image/png,image/jpeg,image/gif,image/webp"
                     class="reg-bild-datei"
                     :data-test="`reg-formular-${bild.rolle}-datei`"
                     @change="bildGewaehlt(bild.rolle, $event)" />
              <DkButton v-if="bild.url" variant="danger" size="md"
                        :data-test="`reg-formular-${bild.rolle}-entfernen`"
                        @click="bildEntfernen(bild.rolle)">
                Entfernen
              </DkButton>
            </div>
            <span class="reg-bild-hinweis">{{ bild.hinweis }}</span>
          </div>
        </div>

        <!-- Felder -->
        <div class="reg-feldbau">
          <div class="reg-feldbau-kopf">
            <span class="reg-feldbau-titel">Felder</span>
            <DkButton variant="secondary" size="md" @click="addFeld">+ Feld</DkButton>
          </div>
          <div v-for="(f, i) in formularFelder" :key="i" class="reg-feldzeile">
            <DkField v-slot="feld" label="Feldbezeichnung" required :error="formularFehler['reg-feld-' + i]"
              :wert="f.label" @update:wert="f.label = $event">
              <input v-bind="feld.feldProps"
                required placeholder="Bezeichnung *" class="dk-ui-eingabe" />
            </DkField>
            <DkSelect v-model="f.feldtyp" :options="feldTypOptionen" aria-label="Feldtyp" />
            <DkCheckbox v-model="f.pflichtfeld" label="Pflicht" />
            <DkButton variant="danger" size="md" @click="formularFelder.splice(i,1)" aria-label="Feld entfernen">×</DkButton>
          </div>
        </div>
       </fieldset>
      </form>
      <template #footer>
        <DkButton variant="secondary" :disabled="formularSpeichert" @click="formularSchliessen">Abbrechen</DkButton>
        <!-- REG-1b: Vorschau — zeigt das Formular wie Besucher es sehen
             (dieselbe Komponente wie die öffentliche Seite), ohne Absenden. -->
        <DkButton variant="secondary" :disabled="formularSpeichert" data-test="reg-formular-vorschau"
                  @click="vorschauOeffnen">
          Vorschau
        </DkButton>
        <DkButton variant="primary" type="submit" form="reg-formular-form" :loading="formularSpeichert">
          {{ formularBearbeitet ? 'Speichern' : 'Anlegen' }}
        </DkButton>
      </template>
    </DkDialog>

    <!-- REG-1b: Vorschau des Anmeldeformulars. Bewusst KEIN DkDialog: dort
         gelten die Verwaltungs-Maße, hier soll die Seite in ihrer echten
         Breite stehen (520 px Karte wie öffentlich, am Handy volle Breite). -->
    <Teleport to="body">
      <div v-if="vorschauOffen" class="reg-vorschau-overlay" @mousedown.self="vorschauSchliessen">
        <div class="reg-vorschau" role="dialog" aria-modal="true"
             aria-label="Vorschau des Anmeldeformulars">
          <div class="reg-vorschau-kopf">
            <h3 class="reg-vorschau-titel">Vorschau — so sehen Besucher das Formular</h3>
            <DkButton variant="secondary" size="md" data-test="reg-vorschau-schliessen"
                      @click="vorschauSchliessen">Schließen</DkButton>
          </div>
          <!-- Dieselbe Komponente wie die öffentliche Registrierungsseite. -->
          <div class="reg-vorschau-buehne">
            <div class="reg-vorschau-seite">
              <div class="reg-vorschau-karte dk-pub-card">
                <DkAnmeldeformular
                  vorschau
                  :felder="vorschauDaten.felder"
                  :mit-kinder="vorschauDaten.mit_kinder"
                  :dokumente="vorschauDaten.dokumente || []"
                  :texte="vorschauDaten.texte || {}"
                  :willkommenstext="vorschauDaten.willkommenstext || ''"
                  :beschreibung="vorschauDaten.beschreibung || ''"
                  :banner-bild="vorschauDaten.banner_bild || ''"
                  :titel="newFormular.mit_kinder ? 'Anmeldung' : 'Mitglied werden'"
                  :subtitel="newFormular.mit_kinder
                    ? 'Melde dich und deine Kinder an. Alle Daten werden sicher gespeichert.'
                    : 'Registriere dich als Gemeindemitglied. Alle Daten werden sicher gespeichert.'"
                />
              </div>
            </div>
          </div>
          <p class="reg-vorschau-fuss">
            Gezeigt werden die Angaben aus dem Editor — Beschreibung und Felder auch ungespeichert.
          </p>
        </div>
      </div>
    </Teleport>

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

    <!-- UX2c: EIN Endgültig-Dialog für beide endgültigen Löschungen dieser
         Seite (Link, Formular) — Titel als Frage, konkrete Folge,
         gefährlicher Knopf am Ende. -->
    <DkEndgueltig
      :model-value="!!bestaetigenFrage"
      :titel="bestaetigenFrage?.titel || 'Endgültig löschen?'"
      :text="bestaetigenFrage?.text || ''"
      :aktion="bestaetigenFrage?.aktion || 'Endgültig löschen'"
      @update:model-value="(wert) => { if (!wert) bestaetigenAntwort(false) }"
      @bestaetigen="bestaetigenAntwort(true)"
    />

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
          <div><strong>Typ:</strong> {{ artText(detailAnmeldung.anmeldungstyp) }}</div>
          <div><strong>Status:</strong> <DkBadge :variant="statusSprache(detailAnmeldung.status).variant">{{ statusSprache(detailAnmeldung.status).wort }}</DkBadge></div>
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
 * Reiter „Anfragen“ des Personen-Bereichs (Konzept Abschnitt 3, Reiter 3).
 * Aufbau: oben der Unterbereich (Anfragen / Links & QR-Codes / Formulare),
 * darunter der Inhalt. UX3j (Entwurf A3): Die Unterbereiche stehen als
 * ZWEITE, kleinere Reiterzeile direkt unter der Reiterzeile — gezeichnet vom
 * Rahmen (`pages/Personen.vue`), die Wahl steht in der Adresse
 * (`#/personen/anfragen[/<unter>]`, menue.js). Das Wort „Anmeldung“ bleibt
 * dem Login vorbehalten.
 * UX-A2b: Der Status der Anfragen (Offen · Aufgenommen · Abgelehnt) ist kein
 * Reiter mehr über den Unterbereichen (dort filterte er auch „Links“ und
 * „Formulare“, wo er nichts bewirkte), sondern eine Chip-Zeile MIT ZAHLEN
 * direkt über der Anfragen-Tabelle. Tabelle und Detailfenster nennen die
 * Zustände in derselben Sprache wie die Chips.
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
import { useLadeSkelett } from '../composables/useLadeSkelett.js'
// UX2g: EINE Quelle fuer angezeigte Fehlertexte statt Floskeln wie
// "Fehler beim Laden" / "Fehler beim Speichern".
import { aktionsfehler } from '../../shared/fehlertexte.js'
// WEB-5b: Adressen unter dem Betriebs-Praefix (DIAKRONOS_BASE_PATH) bauen.
import { apiUrl } from '../../shared/basis.js'
import { showToast } from '../composables/useToast.js'
import { useFormularSchutz } from '../composables/useFormularSchutz.js'
import { pflichtFehler } from '../composables/formularPruefung.mjs'
import { anfragenZahlAuffrischen } from '../composables/useVerwaltung.js'

// Im Personen-Bereich eingebettet: eigener Kopf entfällt, und der
// Unterbereich kommt als EIGENSCHAFT aus dem Rahmen (UX-A2a/UX3j). Die Seite
// schaltet NICHTS selbst um — die Reiterzeile (auch die zweite, kleinere mit
// den Unterbereichen) zeichnet `pages/Personen.vue`; dort steht die Wahl auch
// in der Adresse.
const props = defineProps({
  embedded: { type: Boolean, default: false },
  unterbereich: { type: String, default: '' },
})
const eingebettet = computed(() => props.embedded === true)
import DkPageHeader from '../components/ui/DkPageHeader.vue'
import DkButton from '../components/ui/DkButton.vue'
import DkBadge from '../components/ui/DkBadge.vue'
import DkCard from '../components/ui/DkCard.vue'
import DkDialog from '../components/ui/DkDialog.vue'
import DkSegment from '../components/ui/DkSegment.vue'
import DkField from '../components/ui/DkField.vue'
// UX2c (C1): der EINE Endgültig-Dialog (Frage, Folge, gefährlicher Knopf).
import DkEndgueltig from '../components/ui/DkEndgueltig.vue'
import DkSelect from '../components/ui/DkSelect.vue'
import DkCheckbox from '../components/ui/DkCheckbox.vue'
import DkTable from '../components/ui/DkTable.vue'
import DkEmpty from '../components/ui/DkEmpty.vue'
import DkSkelett from '../components/ui/DkSkelett.vue'
import DkHint from '../components/ui/DkHint.vue'
import RegLinkTeilen from '../components/registrierung/RegLinkTeilen.vue'
// REG-1b: die Anzeige des Anmeldeformulars — DIESELBE Komponente zeigt die
// öffentliche Registrierungsseite. Die Vorschau im Editor ist damit keine
// zweite, driftende Vorlage.
import DkAnmeldeformular from '../../registrierung/components/DkAnmeldeformular.vue'

const loading = ref(true)
// UX2d2: Platzhalter erst nach 300 ms — schnelle Antworten flackern nicht.
const { skelettSichtbar: loadingSkelett } = useLadeSkelett(loading)
const loadingLinks = ref(true)
// UX2d2: Platzhalter erst nach 300 ms — schnelle Antworten flackern nicht.
const { skelettSichtbar: loadingLinksSkelett } = useLadeSkelett(loadingLinks)
const loadingFormulare = ref(true)
// UX2d2: Platzhalter erst nach 300 ms — schnelle Antworten flackern nicht.
const { skelettSichtbar: loadingFormulareSkelett } = useLadeSkelett(loadingFormulare)
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
function bestaetigen(titel, text, aktion = 'Endgültig löschen') {
  bestaetigenFrage.value = { titel, text, aktion }
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

/** Unterbereich (Konzept-Reiter 3): Anfragen | Links & QR-Codes | Formulare.
 *  UX3j: Der Unterbereich kommt IMMER über die Eigenschaft herein und steht
 *  in der Adresse (`#/personen/anfragen[/<unter>]`) — auch wenn die Seite
 *  allein steht, ist der Rahmen (`pages/Personen.vue`) der Ort der Wahl.
 *  Ein eigener Umschalter hier wäre die zweite Reiterzeile für dieselbe
 *  Entscheidung (Befund Manuel 08.11.). */
const UNTERBEREICHE = [
  { value: 'anfragen', label: 'Anfragen' },
  { value: 'links',    label: 'Links & QR-Codes' },
  { value: 'formulare', label: 'Formulare' },
]
const unterbereich = computed(() => {
  const vonAussen = String(props.unterbereich || '')
  return UNTERBEREICHE.some(u => u.value === vonAussen) ? vonAussen : 'anfragen'
})

/** Statusleiter der Anfragen (Konzept-Reiter 3).
 *  UX-A2b: erster Eintrag ist „Alle“ (Korrektur nach Operator-Review) — ohne
 *  ihn gäbe es keinen sichtbaren Zustand für „nichts gefiltert“; ein zweiter
 *  Klick auf den gewählten Chip landet dort (`naechsterChip`). Die Zahl je
 *  Zustand kommt aus DERSELBEN Zählung, die den Filter fährt (`zaehle`). */
const STATUS_LEITER = [
  { wert: 'alle',      label: 'Alle',         leer: 'Keine Anfragen vorhanden' },
  { wert: 'offen',     label: 'Offen',        leer: 'Keine offenen Anfragen' },
  { wert: 'genehmigt', label: 'Aufgenommen',  leer: 'Keine aufgenommenen Anfragen' },
  { wert: 'abgelehnt', label: 'Abgelehnt',    leer: 'Keine abgelehnten Anfragen' },
]

/**
 * UX-A2b: Statusfilter ÜBER der Anfragen-Tabelle.
 *
 * Die frühere Reiterzeile stand über den Unterbereichen und filterte auch
 * dann, wenn „Links“ oder „Formulare“ gewählt war — dort ohne Wirkung
 * (DMB-09a956e8457d). Als Filter direkt über der Tabelle wirkt er genau dort,
 * wo er hingehört; Zahlen machen den Bestand ohne Klick lesbar.
 *
 * UX3j-Nacharbeit (Punkt 1, KERN der Beschwerde Manuels): Dieser Filter war
 * die letzte Chip-Zeile mit dunkel gefülltem Aktiv-Zustand unter „Personen“.
 * Jetzt DERSELBE Baustein wie Liste und Datenschutz (`DkSegment`) mit
 * DERSELBEN Zähler-Schreibweise („Offen 3“). Das frühere Abwählen per zweitem
 * Klick entfällt: „Alle“ ist der sichtbare Ruhezustand (erster Eintrag) —
 * dieselbe Regel wie in der Liste.
 */
const statusFilter = ref('offen')
const statusFilterOptionen = computed(() => STATUS_LEITER.map(s => ({
  value: s.wert,
  label: `${s.label} ${zaehle(s.wert)}`,
})))

function zaehle(art) {
  if (art === 'alle') return anmeldungen.value.length
  if (art === 'offen') return anmeldungen.value.filter(istOffen).length
  if (art === 'genehmigt') return anmeldungen.value.filter(a => a.status === 'Bestätigt').length
  if (art === 'abgelehnt') return anmeldungen.value.filter(a => a.status === 'Abgelehnt').length
  return 0
}

/**
 * UX-A2b: Wort und Kennzeichen eines Anfragestatus — EINE Quelle für Tabelle
 * und Detailfenster, in derselben Sprache wie die Filterchips.
 *
 * Die Filter heissen „Offen · Aufgenommen · Abgelehnt“; die Tabelle zeigte
 * davor die rohen Server-Werte („Anmeldeanfrage“, „Ausstehend“,
 * „Bestätigt“) — derselbe Sachverhalt hiess an zwei Stellen anders
 * (Nebenbefund aus dem Entwurf). Die WORDLISTE bleibt hier: `statussprache.mjs`
 * kennt Plan- und Prüfstatus, keine Anmeldestati — ein Eintrag dort wäre ein
 * Fremdwert in einem Modul, das Pläne beschreibt.
 */
const ANMELDESTATUS_SPRACHE = {
  'Anmeldeanfrage': { wort: 'Offen',       variant: 'warn' },
  'Ausstehend':     { wort: 'Offen',       variant: 'warn' },
  'Bestätigt':      { wort: 'Aufgenommen', variant: 'ok' },
  'Abgelehnt':      { wort: 'Abgelehnt',   variant: 'err' },
  'Warteliste':     { wort: 'Warteliste',  variant: 'info' },
}
function statusSprache(status) {
  return ANMELDESTATUS_SPRACHE[status] || { wort: status || '–', variant: 'neutral' }
}

/** UX-A2b: Anmeldetyp in Klartext („Mitglied“, „Gast“, …) statt des rohen
 *  Select-Werts („Mitglied-Registrierung“). Unbekannte Werte bleiben stehen —
 *  nie ein geratener Name. */
const ANMELDETYP_SPRACHE = {
  'Mitglied-Registrierung': 'Mitglied',
  'Gast-Anmeldung': 'Gast',
}
function artText(typ) {
  return ANMELDETYP_SPRACHE[typ] || typ || '–'
}

/** Ist die Anfrage noch offen (aufnehmbar/ablehnbar)? */
function istOffen(a) {
  return OFFENE_ANMELDESTATI.includes(a.status)
}

const anmeldungSpalten = [
  { key: 'datum', label: 'Datum' },
  { key: 'name', label: 'Name' },
  // UX-A2b: Die Spalte hiess „Art“ und zeigte den rohen Wert
  // („Mitglied-Registrierung“, „Gast-Anmeldung“). Vorlage und Entwurf A2
  // nennen sie „Typ“.
  { key: 'typ', label: 'Typ' },
  { key: 'hinweis', label: 'Hinweis' },
  { key: 'status', label: 'Status' },
  // FIX-4: Aktionen-Spalte — `aktion: true` gibt dem `<th>` und der Zelle
  // `.is-aktion` (Mindestbreite, Umbruch statt Überlagerung am Handy).
  { key: 'aktionen', label: 'Aktionen', aktion: true },
]
const formularSpalten = [
  { key: 'bez', label: 'Bezeichnung' },
  { key: 'gaeste', label: 'Gäste' },
  { key: 'kinder', label: 'Kinder' },
  { key: 'felder', label: 'Felder' },
  { key: 'aktionen', label: 'Aktionen', aktion: true },
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

/**
 * Warteliste-Anfragen gehören unter „Alle“ (Operator-Review): sie sind weder
 * offen (nicht aufnehmbar/ablehnbar) noch aufgenommen noch abgelehnt und
 * verschwänden sonst in einem unsichtbaren Zustand.
 */
const filteredAnmeldungen = computed(() => {
  if (statusFilter.value === 'offen') return anmeldungen.value.filter(istOffen)
  if (statusFilter.value === 'genehmigt') return anmeldungen.value.filter(a => a.status === 'Bestätigt')
  if (statusFilter.value === 'abgelehnt') return anmeldungen.value.filter(a => a.status === 'Abgelehnt')
  return anmeldungen.value
})

const leerText = computed(() => (
  STATUS_LEITER.find(s => s.wert === statusFilter.value)?.leer ?? 'Keine Anfragen vorhanden'
))

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
    showToast(aktionsfehler('laden', null), 'error')
  } finally {
    loading.value = false
    loadingLinks.value = false
  }

  try {
    const fRes = await apiCall('diakronos.diakonos.api.admin_hub.get_anmeldeformulare')
    formulare.value = (fRes.message || fRes).formulare || []
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
      // UX-A2a2: Aufgenommen heißt eine offene Anfrage weniger — die
      // gemeinsame Kennzahl (Seitenleiste + Bereichsliste) sofort nachziehen,
      // statt bis zu einer Minute eine falsche Zahl zu zeigen.
      anfragenZahlAuffrischen()
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
      // UX-A2a2: abgelehnt heißt eine offene Anfrage weniger — Kennzahl sofort
      // nachziehen (Seitenleiste und Bereichsliste teilen den Stand).
      anfragenZahlAuffrischen()
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
/**
 * M-1: die unter „Einstellungen → Registrierung“ gepflegten Vorgaben.
 *
 * UI-R10b: `null` heißt „noch nicht bekannt / nicht lesbar“. Dann bleibt das
 * Ablaufdatum LEER — leer ist die Vorgabe (der Server setzt sie beim Anlegen
 * ein) — und das Formular sagt „Laufzeit: Vorgabe der Gemeinde“. Eine feste
 * Zahl im Frontend (früher 30 Tage) ist verboten: sie wich still von der
 * Gemeinde ab, sobald die Mitgliederverwaltung die Einstellungen nicht lesen
 * durfte.
 */
const linkVorgaben = ref(null)
const leererLink = () => {
  // M-1: neue Links werden mit den Gemeinde-Vorgaben vorbelegt, damit der
  // Hinweis im Einstellungsbereich stimmt. Der Server wendet dieselben
  // Vorgaben an, wenn hier nichts eingetragen wird.
  // UI-R10b: ohne bekannte Vorgabe bleibt `gueltig_bis` LEER (= Vorgabe), es
  // wird nie eine Zahl geraten.
  const v = linkVorgaben.value
  const gueltig = v && v.laufzeitTage > 0
    ? new Date(Date.now() + v.laufzeitTage * 86400000).toISOString().slice(0, 10)
    : ''
  return {
    bezeichnung: '', typ: 'Mitglied-Registrierung',
    gueltig_bis: gueltig, max_anmeldungen: (v && v.maxAnmeldungen) || 0, anmeldeformular_id: '',
    // REG-1b: „gültig ab“ — leer heisst SOFORT nutzbar (Server: NULL).
    gueltig_ab: '',
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

/**
 * UI-R10b: Link-Vorgaben laden — über den EIGENEN Lese-Endpunkt
 * (`registrierungslink_api.get_link_vorgaben`), den auch die
 * Mitgliederverwaltung darf (dieselbe Prüfung wie `create_link`, R-12f).
 *
 * Vorher stand hier `gemeinde_get_einstellungen` — das ist Kern-Admin
 * (`gemeinde._angemeldeter_admin`), die Mitgliederverwaltung bekam 403, der
 * Fehler blieb still und neue Links fielen auf fest eingebaute 30 Tage zurück.
 *
 * Schlägt der Abruf fehl, bleibt `linkVorgaben` `null`: das Datumsfeld bleibt
 * LEER (= der Server wendet die Vorgabe an) und das Formular schreibt
 * „Laufzeit: Vorgabe der Gemeinde“. Nie eine feste Zahl.
 */
async function ladeLinkVorgaben() {
  try {
    const res = await apiCall('diakronos.diakonos.api.registrierungslink_api.get_link_vorgaben', {})
    const d = res?.message || res
    if (!d || d.link_laufzeit_tage === undefined) throw new Error('keine Vorgaben')
    linkVorgaben.value = {
      laufzeitTage: Number(d.link_laufzeit_tage) || 0,
      maxAnmeldungen: Number(d.link_max_anmeldungen) || 0,
    }
  } catch {
    // Nicht lesbar: keine Zahl raten — leer heißt Vorgabe (Server entscheidet).
    linkVorgaben.value = null
  }
}
/**
 * UI-R10b: der Satz unter dem Zeitraum. Er nennt die Vorgabe NUR, wenn sie
 * gelesen wurde; sonst steht dort ausdrücklich „Vorgabe der Gemeinde“ —
 * dieselbe Aussage, die das leere Feld macht (der Server setzt sie ein).
 */
const laufzeitHinweis = computed(() => {
  const v = linkVorgaben.value
  if (!v || !(v.laufzeitTage > 0)) return 'Laufzeit: Vorgabe der Gemeinde.'
  return `Laufzeit: ${v.laufzeitTage} Tage ab heute (Vorgabe der Gemeinde) — frei änderbar.`
})
/** Hilfe am Feld „Gültig bis“: leer heißt Vorgabe, nie eine geratene Zahl. */
const ohneAblaufHinweis = computed(() => (linkVorgaben.value
  ? 'Leer = Laufzeit der Gemeinde-Vorgabe.'
  : 'Leer = Laufzeit: Vorgabe der Gemeinde.'))

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
    case 'bevorstehend': return 'Startet später'
    case 'voll':       return 'Voll'
    case 'inaktiv':    return 'inaktiv'
    case 'aktiv':      return 'aktiv'
    default:           return l.aktiv ? 'aktiv' : 'inaktiv'
  }
}

function zustandVariante(l) {
  switch (l.zustand) {
    case 'abgelaufen': return 'err'
    case 'bevorstehend': return 'info'
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
  if (!await bestaetigen(`Registrierungslink „${l.bezeichnung}“ löschen?`,
    `${folgen} Der Link und seine Adresse verschwinden dauerhaft — das lässt sich nicht rückgängig machen.`,
    'Link endgültig löschen')) return
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
// REG-1b: Beschreibung und Bilder gehören zum Formularkopf (Backend REG-1a:
// `beschreibung`, `bannerbild`, `hintergrundbild`).
const leeresFormular = () => ({
  bezeichnung: '', mit_gaesten: false, mit_kinder: false, beschreibung: '',
})
const newFormular = ref(leeresFormular())
const formularFelder = ref([])
const formularSpeichert = ref(false)
const formularFehler = ref({})
// OP-ADMIN-19: `null` = neues Formular; sonst der `name` des Formulars, das
// gerade bearbeitet wird. Ohne diesen Wert gab es keinen Weg, ein bestehendes
// Formular zu öffnen oder zu ändern.
const formularBearbeitet = ref(null)

// ── REG-1b: Banner, Hintergrund und Vorschau ──────────────────────────────
/** Bildrollen des Formulars — Rollennamen wie in der API (`/bild/<rolle>`). */
const BILD_ROLLEN = ['banner', 'hintergrund']
/** Anzeige der beiden Bildfelder (URL = Vorschau der Verwaltung, `/files/…`). */
const formularBilder = ref({ banner: '', hintergrund: '' })
/** Gerade gewählte, noch nicht hochgeladene Datei je Rolle. */
const bildDateien = ref({ banner: null, hintergrund: null })
/** Eingabeelemente je Rolle — nach dem Übernehmen leeren. */
const bildEingabe = ref({})
/** Rollen, deren Bild beim Speichern entfernt werden soll. */
const bilderEntfernen = ref([])
const bildFehler = ref('')

const bildFelder = computed(() => [
  {
    rolle: 'banner',
    titel: 'Banner',
    url: formularBilder.value.banner,
    hinweis: 'Steht über dem Formularkopf. PNG, JPEG, GIF oder WebP.',
  },
  {
    rolle: 'hintergrund',
    titel: 'Hintergrund',
    url: formularBilder.value.hintergrund,
    hinweis: 'Liegt gedämpft hinter der Anmeldeseite. Wird beim Speichern übernommen.',
  },
])

function bilderZuruecksetzen() {
  formularBilder.value = { banner: '', hintergrund: '' }
  bildDateien.value = { banner: null, hintergrund: null }
  bilderEntfernen.value = []
  bildFehler.value = ''
  for (const rolle of BILD_ROLLEN) {
    const el = bildEingabe.value[rolle]
    if (el) el.value = ''
  }
}

/** Grenze eines Formularbildes in Bytes — aus dem Boot-Objekt, also derselbe
 *  Wert, den der Server beim Upload zieht (`api.frappe_core.upload_limit`).
 *  Fehlt die Angabe (0), entscheidet der Server allein.
 *
 *  Absichtlich eine Funktion: der Wert wird erst beim Pruefen gelesen, nicht
 *  beim Laden des Moduls (die Seite laeuft auch in Tests ohne `window`). */
function bildMaxBytes() {
  return Number(window.__DIakonosBOOT?.bild_upload_max_bytes) || 0
}

/** Grenze als Text „10 MB“ (bzw. mit einer Nachkommastelle, wenn noetig). */
function bildMaxText(bytes) {
  if (!bytes) return ''
  const mb = bytes / (1024 * 1024)
  const zahl = Number.isInteger(mb) ? String(mb) : mb.toFixed(1).replace('.', ',')
  return `${zahl} MB`
}

/** Datei gewählt: nur Vorschau im Editor; hochgeladen wird beim Speichern. */
function bildGewaehlt(rolle, ereignis) {
  const datei = ereignis?.target?.files?.[0] || null
  bildDateien.value[rolle] = datei
  bildFehler.value = ''
  if (!datei) return
  if (!/^image\/(png|jpeg|gif|webp)$/.test(datei.type)) {
    bildFehler.value = 'Nur PNG, JPEG, GIF oder WebP — andere Dateien lehnt der Server ab.'
    bildDateien.value[rolle] = null
    return
  }
  // REG-1c (4): Groesse VOR dem Upload pruefen — sonst laedt der Besucher
  // minutenlang hoch, nur damit der Server am Ende ablehnt. Die Grenze ist
  // derselbe Wert, den `upload_file` zieht (`bild_upload_max_bytes`).
  const grenze = bildMaxBytes()
  if (grenze && datei.size > grenze) {
    bildFehler.value = `Das Bild ist zu groß — erlaubt sind max. ${bildMaxText(grenze)}. `
      + 'Bitte ein kleineres Bild wählen.'
    bildDateien.value[rolle] = null
    const el = ereignis?.target
    if (el) el.value = ''
    return
  }
  // „Entfernen“ zurücknehmen: die neue Datei ersetzt das alte Bild.
  bilderEntfernen.value = bilderEntfernen.value.filter(r => r !== rolle)
  if (typeof URL !== 'undefined' && URL.createObjectURL) {
    formularBilder.value = { ...formularBilder.value, [rolle]: URL.createObjectURL(datei) }
  }
}

function bildEntfernen(rolle) {
  bildDateien.value = { ...bildDateien.value, [rolle]: null }
  formularBilder.value = { ...formularBilder.value, [rolle]: '' }
  const el = bildEingabe.value[rolle]
  if (el) el.value = ''
  if (!bilderEntfernen.value.includes(rolle)) {
    bilderEntfernen.value = [...bilderEntfernen.value, rolle]
  }
}

// ── Vorschau (REG-1b) ─────────────────────────────────────────────────────
const vorschauOffen = ref(false)
const vorschauDaten = ref({ felder: [], mit_kinder: 0, dokumente: [], texte: {}, beschreibung: '' })
const vorschauLaedt = ref(false)

/** Die Felder so, wie sie gespeichert würden (ohne leere Bezeichnungen). */
function felderFuerAnzeige() {
  return formularFelder.value
    .filter(f => String(f.label || '').trim())
    .map(f => ({
      label: String(f.label).trim(),
      feldtyp: f.feldtyp || 'Text',
      optionen: f.optionen || '',
      pflichtfeld: f.pflichtfeld ? 1 : 0,
      fuer_gaeste: f.fuer_gaeste ? 1 : 0,
      fuer_kinder: f.fuer_kinder ? 1 : 0,
    }))
}

/**
 * Vorschau öffnen. Die Daten kommen vom Server (`get_formular_vorschau`) —
 * derselbe Weg, den die öffentliche Seite nimmt (`_formular_felder`), inklusive
 * Beschreibung, Bildpfaden und Einwilligungstexten. Damit die Vorschau beim
 * Tippen mitläuft, werden die gerade im Editor stehenden Angaben mitgeschickt.
 */
async function vorschauOeffnen() {
  if (vorschauLaedt.value) return
  vorschauLaedt.value = true
  try {
    const antwort = await apiCall('diakronos.diakonos.api.registrierung_vorschau.get_formular_vorschau', {
      formular_id: formularBearbeitet.value || '',
      felder: JSON.stringify(felderFuerAnzeige()),
      mit_kinder: newFormular.value.mit_kinder ? 1 : 0,
      mit_gaesten: newFormular.value.mit_gaesten ? 1 : 0,
      beschreibung: newFormular.value.beschreibung || '',
    })
    const daten = antwort?.message ?? antwort
    vorschauDaten.value = {
      felder: Array.isArray(daten?.felder) ? daten.felder : felderFuerAnzeige(),
      mit_kinder: daten?.mit_kinder ? 1 : 0,
      dokumente: Array.isArray(daten?.dokumente) ? daten.dokumente : [],
      texte: daten?.texte || {},
      willkommenstext: daten?.willkommenstext || '',
      beschreibung: daten?.beschreibung || newFormular.value.beschreibung || '',
      banner_bild: daten?.banner_bild || '',
      hintergrund_bild: daten?.hintergrund_bild || '',
    }
    // Noch nicht gespeicherte Bilder: die lokale Vorschau ist besser als nichts.
    if (!vorschauDaten.value.banner_bild && formularBilder.value.banner?.startsWith('blob:')) {
      vorschauDaten.value.banner_bild = formularBilder.value.banner
    }
    vorschauOffen.value = true
  } catch (err) {
    showToast(formularMeldung(err, 'Die Vorschau konnte nicht geladen werden.'), 'error')
  } finally {
    vorschauLaedt.value = false
  }
}

function vorschauSchliessen() {
  vorschauOffen.value = false
}

const formularSchutz = useFormularSchutz(
  () => [newFormular.value, formularFelder.value], () => formularSpeichert.value,
)
function formularOeffnen() {
  newFormular.value = leeresFormular()
  formularFelder.value = []
  formularFehler.value = {}
  formularBearbeitet.value = null
  bilderZuruecksetzen()
  formularSchutz.merken()
  showCreateFormular.value = true
}

/** OP-ADMIN-19: Ein Formular oeffnen, um es zu aendern.
 *  Die Felder kommen vom Server (`get_anmeldeformular_felder`) — vorher gab
 *  es diesen Weg gar nicht, ein Formular war damit nicht aenderbar. */
async function formularBearbeiten(f) {
  formularFehler.value = {}
  bilderZuruecksetzen()
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
      beschreibung: daten?.beschreibung || '',
    }
    // REG-1b: Banner und Hintergrund sind eigene Felder des Kopfes; sie kommen
    // aus `get_anmeldeformular_felder` (banner_bild_url/hintergrund_bild_url,
    // Pfade unter `/files/…` — für die Verwaltung angemeldet erreichbar).
    formularBilder.value = {
      banner: daten?.banner_bild_url || '',
      hintergrund: daten?.hintergrund_bild_url || '',
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
    'Das Anmeldeformular und seine Felder werden dauerhaft entfernt. Das lässt sich nicht '
      + 'rückgängig machen; es geht nur, solange kein Registrierungslink mehr darauf verweist.',
    'Formular endgültig löschen',
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
    // REG-1b: Bilder H O C H L A D E N, bevor der Kopf geschrieben wird — der
    // Server nimmt nur Dateinamen an, die vorher über `upload_file` entstanden
    // sind (`pruefe_bilddatei`). Erst danach wird zugeordnet.
    const kopf = {
      beschreibung: newFormular.value.beschreibung || '',
    }
    // REG-1c: bei einem NEUEN Formular gibt es die Kennung noch nicht — sie
    // entsteht erst beim Anlegen. Die Datei muss aber an genau dieses Formular
    // angehängt sein, sonst lehnt der Server sie ab. Deshalb: erst anlegen,
    // dann hochladen, dann in EINEM Aufruf zuordnen (siehe unten).
    const neuesFormular = !formularBearbeitet.value
    if (neuesFormular) {
      const res = await apiCall('diakronos.diakonos.api.admin_hub.create_anmeldeformular', {
        bezeichnung: newFormular.value.bezeichnung,
        mit_gaesten: newFormular.value.mit_gaesten ? 1 : 0,
        mit_kinder: newFormular.value.mit_kinder ? 1 : 0,
      })
      if (!res?.success) throw new Error('Das Formular konnte nicht angelegt werden.')
      formularBearbeitet.value = res.id
    }
    const formularId = formularBearbeitet.value
    bildFehler.value = ''
    for (const rolle of BILD_ROLLEN) {
      const datei = bildDateien.value[rolle]
      if (!datei) continue
      try {
        const hoch = await uploadBild(datei, formularId)
        const dateiname = String(hoch?.file_url || '').split('/').pop()
        if (!dateiname) throw new Error('Der Upload lieferte keinen Dateinamen.')
        kopf[rolle === 'banner' ? 'banner_bild_datei' : 'hintergrund_bild_datei'] = dateiname
        bildDateien.value = { ...bildDateien.value, [rolle]: null }
      } catch (err) {
        // Das Formular wird trotzdem gespeichert, aber der Grund steht sichtbar
        // im Fenster — ein stillschweigend fehlendes Bild wäre schlimmer.
        bildFehler.value = formularMeldung(err, 'Das Bild konnte nicht hochgeladen werden.')
      }
    }
    if (bilderEntfernen.value.length) {
      kopf.bilder_entfernen = bilderEntfernen.value.join(',')
    }

    if (formularBearbeitet.value) {
      // OP-ADMIN-19: aendern — Kopf und Felder in EINEM Aufruf, damit ein
      // halb gespeichertes Formular nicht entstehen kann.
      await apiCall('diakronos.diakonos.api.admin_hub.update_anmeldeformular', {
        formular_id: formularBearbeitet.value,
        bezeichnung: newFormular.value.bezeichnung,
        mit_gaesten: newFormular.value.mit_gaesten ? 1 : 0,
        mit_kinder: newFormular.value.mit_kinder ? 1 : 0,
        felder_json: JSON.stringify(cleanFelder),
        ...kopf,
      })
      showToast('Formular gespeichert')
    } else {
      // REG-1c: das Formular wurde oben bereits angelegt (die Bilder brauchen
      // seine Kennung). Felder, Beschreibung und Bilder sind im Aufruf oben
      // mitgeschrieben — hier bleibt nur die Rueckmeldung.
      showToast('Formular erstellt')
    }
    if (bildFehler.value) {
      // Der Text bleibt stehen (Fenster schließt nicht) — nichts wurde gelöscht.
      formularFehler.value = { speichern: bildFehler.value }
      return
    }
    showCreateFormular.value = false
    newFormular.value = leeresFormular()
    formularFelder.value = []
    formularBearbeitet.value = null
    bilderZuruecksetzen()
    formularSchutz.merken()
    await fetchData()
  } catch (err) {
    formularFehler.value = { speichern: formularMeldung(err, 'Das Formular konnte nicht gespeichert werden. Bitte erneut versuchen.') }
  } finally {
    formularSpeichert.value = false
  }
}

/**
 * REG-1b: Datei über den vorhandenen Weg hochladen (`upload_file`, Multipart).
 *
 * Bewusst rohes `fetch`: `apiCall` erzwingt JSON. Der CSRF-Kopf ist Pflicht —
 * ohne ihn lehnt der Server den Schreibzugriff ab (wie beim Anhängen von
 * Lied-Material, `usePlanrahmen.uploadDatei`).
 *
 * REG-1c (Punkt 1): `doctype`/`docname` werden MITGESCHICKT. Der Server nimmt
 * ein Bild nur noch an, wenn der `File`-Datensatz an GENAU DIESES
 * Anmeldeformular angehängt ist (`formularbilder.pruefe_bilddatei`). Ohne die
 * beiden Felder entstünde eine Datei ohne Bezug — die Zuordnung wäre unmöglich.
 */
async function uploadBild(datei, formularId) {
  const csrf = document.querySelector('meta[name="csrf-token"]')?.content
             || window.__DIakonosBOOT?.csrf_token || ''
  const form = new FormData()
  form.append('file', datei, datei.name)
  form.append('is_private', 'true')
  form.append('doctype', 'Anmeldeformular')
  form.append('docname', formularId)
  const res = await fetch(apiUrl('upload_file'), {
    method: 'POST',
    headers: { 'X-Frappe-CSRF-Token': csrf },
    body: form,
  })
  let daten = null
  try { daten = await res.json() } catch { daten = null }
  if (!res.ok || daten?.exc) {
    throw new Error(formularMeldung(daten, `Das Bild konnte nicht hochgeladen werden (HTTP ${res.status}).`))
  }
  return daten?.message || daten
}

// ── Details ───────────────────────────────────────────────────────────────

const detailAnmeldung = ref(null)
function showDetail(a) { detailAnmeldung.value = a }

/**
 * UX3j: Die Hauptaktionen der Unterbereiche („Neuer Link“ / „Neues
 * Formular“) stehen im EINEN Seitenkopf von `pages/Personen.vue`. Der Rahmen
 * ruft dieselben Funktionen hier auf — ein Knopf, eine Umsetzung, kein
 * zweiter Dialog.
 */
defineExpose({ linkOeffnen, formularOeffnen })

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

/** Anfragestatus → Kennzeichen-Variante.
 *  UX-A2b: ersetzt durch `statusSprache` (Wort UND Kennzeichen in derselben
 *  Sprache wie die Filterchips). */

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

/* UX-A2b: Statusfilter (Chip-Zeile) direkt über der Anfragen-Tabelle. Abstand
   wie bei den übrigen Filterzeilen (DES-01: 8 px bis zur Liste). Das seitliche
   Am Handy bricht der Segmentschalter um (DkSegment) — hier bleibt nur der
   Abstand. */
.reg-statusfilter { margin-bottom: var(--sp-3); }

/* OP-UI-19: Die eigene Ladeform (reg-skelett) ist durch DkSkelett ersetzt. */

.reg-jetzt { white-space: nowrap; }
.reg-muted { color: var(--muted); }

/* FIX-4: `.reg-aktionen` ist der Wrapper IN der Aktionszelle (Anfragen-
   Tabelle) — er hält die Knöpfe als Flex-Zeile mit Token-Abstand. Auf einem
   `<td>` selbst war `display:flex` wirkungslos (ein `<td>` ist keine
   Flex-Zelle); die Aktionsspalte hält jetzt DkTable über `td.is-aktion`. */
.reg-aktionen { display: flex; flex-wrap: wrap; align-items: center; gap: var(--sp-2); }

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
/* UX1f: „Löschen“ (dauerhaft) ist eine Nebenaktion der Linkliste — die
   Gefahr traegt die Schriftfarbe, nicht ein zweiter gefuellter Knopf neben
   „Verlängern“ (S1, wie dk-mod-loeschen-schrift im Kalender). */
.reg-loeschen-schrift { color: var(--err); }
.reg-loeschen-schrift:hover:not(:disabled) { color: var(--err); }

.reg-eingaben { border: 0; margin: 0; padding: 0; min-width: 0; }
.reg-schalter { display: flex; align-items: flex-start; gap: var(--sp-2); font-size: var(--fs-sm); }
.reg-schalter input { margin-top: var(--sp-1); flex-shrink: 0; }
.reg-formular { display: flex; flex-direction: column; gap: var(--sp-3); }
.reg-kaestchen { display: flex; gap: var(--sp-4); flex-wrap: wrap; }
/* REG-1b: „Gültig ab“ und „Gültig bis“ nebeneinander (ein Zeitraum), am Handy
   untereinander — die Felder bleiben in jedem Fall bedienbar. */
.reg-zeitraum { display: grid; grid-template-columns: 1fr 1fr; gap: var(--sp-3); }
@media (max-width: 520px) { .reg-zeitraum { grid-template-columns: 1fr; } }
.reg-feldbau { margin-top: var(--sp-3); }
.reg-feldbau-kopf { display: flex; justify-content: space-between; align-items: center; margin-bottom: var(--sp-3); }
.reg-feldbau-titel { font-size: var(--fs-sm); font-weight: 600; color: var(--text); }
.reg-feldzeile { display: grid; grid-template-columns: 1fr 120px 80px 40px; gap: var(--sp-2); align-items: center; margin-bottom: var(--sp-2); }
@media (max-width: 520px) { .reg-feldzeile { grid-template-columns: 1fr; } }

.reg-detail { display: flex; flex-direction: column; gap: var(--sp-3); }

/* REG-1b: Banner/Hintergrund im Formular-Editor. */
.reg-bilder { display: grid; grid-template-columns: 1fr 1fr; gap: var(--sp-3); }
@media (max-width: 520px) { .reg-bilder { grid-template-columns: 1fr; } }
.reg-bild { display: flex; flex-direction: column; gap: var(--sp-2); }
.reg-bild-titel { font-size: var(--fs-sm); font-weight: 600; color: var(--text); }
.reg-bild-vorschau {
  display: block; width: 100%; max-height: 120px; object-fit: cover;
  border: 1px solid var(--line); border-radius: var(--radius);
  background: var(--surface-2);
}
.reg-bild-aktionen { display: flex; flex-wrap: wrap; gap: var(--sp-2); align-items: center; }
.reg-bild-datei { font-size: var(--fs-sm); color: var(--text); max-width: 100%; }
.reg-bild-hinweis { font-size: var(--fs-sm); color: var(--muted); }

/* REG-1b: Die Vorschau steht in der Breite der öffentlichen Seite.
   Die Karte selbst bringt ihre Maße mit (`dk-pub-card`, 520 px, am Handy
   volle Breite) — hier nur die Bühne drumherum. */
.reg-vorschau-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  background: color-mix(in oklch, var(--dk-navy-900) 60%, transparent);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--sp-4);
}
.reg-vorschau {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-md);
  width: 100%;
  max-width: 760px;
  max-height: 92vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.reg-vorschau-kopf {
  display: flex; align-items: center; justify-content: space-between;
  gap: var(--sp-3); padding: var(--sp-4);
  border-bottom: 1px solid var(--divider);
}
.reg-vorschau-titel { font-size: var(--fs-h4); font-weight: var(--fw-h); color: var(--text); margin: 0; }
.reg-vorschau-buehne { overflow: auto; background: var(--bg); padding: var(--sp-5) var(--sp-4); }
.reg-vorschau-seite { display: flex; justify-content: center; }
/* Die Karte in der Vorschau ist DIESELBE wie oeffentlich (`dk-pub-card`):
   Breite, Innenabstand, Rahmen und Farbe kommen aus `registrierung/App.vue`
   (dort global, also auch hier gueltig). Hier nur der Schatten fuer die Buehne. */
.reg-vorschau-karte { box-shadow: var(--shadow-md); box-sizing: border-box; }
.reg-vorschau-fuss {
  margin: 0; padding: var(--sp-3) var(--sp-4);
  border-top: 1px solid var(--divider);
  font-size: var(--fs-sm); color: var(--muted);
}
/* Inhaltsumbruch, kein Layout: die Formular-VORSCHAU (Dialog im Bearbeiten-
   Bereich) füllt am schmalen Gerät die Fläche — das ist keine App-Layout-
   Umschaltung, die Vorschau-Bühne liegt in einem Dialog. */
@media (max-width: 640px) {
  .reg-vorschau-overlay { padding: 0; }
  .reg-vorschau { max-width: none; height: 100vh; max-height: none; border-radius: 0; }
  .reg-vorschau-buehne { padding: var(--sp-4) var(--sp-3); }
}
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
