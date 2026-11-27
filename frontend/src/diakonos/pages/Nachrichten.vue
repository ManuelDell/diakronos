<template>
  <!-- CHAT-3a — Bereich „Nachrichten“ (Chat-Konzept 6.2 Variante B, 10.1/10.2).
       Desktop: Liste links, Verlauf rechts. Handy: zwei Ansichten — die Liste
       unter `#/nachrichten`, der Verlauf unter `#/nachrichten/<gespraech>`
       (eine Ebene, kein Seitenbaum; Zurück führt zur Liste). -->
  <div
    class="dk-screen dk-screen-wide dk-screen-enter dk-chat dk-chat--fuellt"
    :class="{ 'is-handy': istHandyLage, 'is-gespraech': Boolean(offeneKennung) }"
  >
    <!-- CHAT-3a-4 (SOLL 3): Am HANDY mit offenem Gespräch gibt es NUR den
         Verlaufskopf (Zurück, Titel, Untertitel, Stumm als Symbolknopf) —
         Brotkrumen und Seitenkopf stehen dort nicht, sonst stünde der Titel
         dreifach. Am Desktop bleibt der Seitenkopf: er trägt den Bereich
         („Nachrichten“), der Verlaufskopf das Gespräch — keine Doppelung.

         LEISTE-1 (Manuel 23.11., DMB-4971): Den Seitenkopf gibt es GAR NICHT
         mehr. „Obere Leiste mit Suche kann weg, Überschrift ‚Nachrichten‘ kann
         weg.“ Die Seite läuft im Vollbild (router.js `vollbildRoute`); Suche,
         Glocke und Plus stehen in ihrer eigenen Zeile (`.dk-chat-leiste`). -->

    <!-- LEISTE-1: Handy-Kopf der Vollbild-Seite — ☰ (Seitenleiste), Suchfeld,
         Glocke, Plus. Am Desktop gibt es diese Zeile nicht: dort sitzt die
         Suche oben in der Gesprächsliste, die Glocke in der Seitenleiste. -->
    <div
      v-if="modulAn && istHandyLage && !offeneKennung"
      class="dk-chat-leiste"
      :class="{ 'is-suche': sucheOffen }"
    >
      <MenueKnopf @oeffnen="$emit('open-menu')" />
      <!-- Am Handy sitzt die eine Suche hier, am Desktop oben in der Liste —
           je Lage genau EINE Instanz (dieselbe `ref`), nie beide. Mit offenem
           Gespräch trägt am Handy der Verlaufskopf (Zurück, Titel) die Zeile. -->
      <ChatSuche
        ref="sucheEl"
        class="dk-chat-leiste-suche"
        :gespraeche="gespraeche"
        :start-begriff="suchBegriff"
        @sucht="begriffGeaendert"
        @springen="springen"
      />
      <Glocke gross />
      <DkAktionen
        :eintraege="neueEintraege"
        label="Neue Nachricht oder neue Runde"
        menue-label="Neue Nachricht oder neue Runde"
        kennung="chat-neu"
      />
    </div>

    <!-- Modul aus (oder kein Leserecht): EIN Hinweis, keine leere Liste. -->
    <DkCard v-if="!modulAn" flach>
      <DkEmpty icon="✉" :title="MODUL_AUS.titel" :text="MODUL_AUS.text" />
    </DkCard>

    <template v-else>
      <div class="dk-chat-bereich">
        <!-- ── Liste ──────────────────────────────────────────────────── -->
        <!-- CHAT-3c-2 (SOLL 4): Am Handy ist die jeweils andere Spalte
             ausgeblendet. Läuft die Suche, ist die TREFFERFLÄCHE die sichtbare
             Spalte — also NICHT diese Spalte ausblenden, sondern den Verlauf
             (`nur-handy-aus` an der Verlaufsspalte). Am Desktop (zweispaltig)
             stehen ohnehin beide da. -->
        <div
          class="dk-chat-liste-spalte"
          :class="{ 'nur-handy-aus': Boolean(kennung) }"
        >
          <!-- Fehler der Liste (403 → „kein Zugriff“, sonst Katalogtext).
               CHAT-7a-UI-2: Er steht in SEINER Spalte, nicht über dem ganzen
               Bereich — sonst verschwände mit der Liste auch der offene
               Verlauf samt Eingabe, und man könnte nicht mehr schreiben, weil
               eine Abfrage danebengescheitert ist. -->
          <DkCard v-if="listenFehler" flach>
            <DkEmpty
              icon="⚠"
              :title="listenFehler.titel"
              :text="listenFehler.text"
              :erneut-versuchen="laden"
            />
          </DkCard>
          <template v-else>
            <!-- CHAT-11b (Review R1/6): „Diese Nachricht gibt es nicht mehr.“
                 steht HIER — in der Spalte, die auch die Listenansicht zeigt
                 (ein gescheiterter Sprung führt oft gerade nicht in einen
                 offenen Verlauf). Ruhig, role="status", keine Alarmfarbe. -->
            <p
              v-if="sprungHinweis && !offeneKennung"
              class="dk-chat-hinweis dk-chat-sprungweg dk-chat-sprungweg--liste"
              role="status"
            >{{ sprungHinweis }}</p>
            <DkSkelett v-if="skelettSichtbar" form="zeilen" :anzahl="5" text="Gespräche werden geladen …" />
            <template v-else>
              <!-- CHAT-3c: EIN Suchfeld, zwei Trefferarten. Ist die Suche offen
                   (`#/nachrichten/suche?q=…`), ersetzt ihre Trefferfläche die
                   Liste; „Zurück“/Leeren schließt sie. Ein Treffer ist ein
                   normaler Link — der Browser springt, der Router folgt
                   (CHAT-3c-2, MUSS A).
                   LEISTE-1: Am HANDY steht das Suchfeld oben im eigenen Kopf
                   (`.dk-chat-leiste`) — diese Spalte zeigt es dort nicht ein
                   zweites Mal. Am Desktop ist es der Kopf der Liste. -->
              <ChatSuche
                v-if="!istHandyLage"
                ref="sucheEl"
                :gespraeche="gespraeche"
                :start-begriff="suchBegriff"
                @sucht="begriffGeaendert"
                @springen="springen"
              />
              <template v-if="!sucheOffen">
                <DkEmpty
                  v-if="!gruppen.length"
                  icon="✉"
                  :title="LISTE_LEER.titel"
                  :text="LISTE_LEER.text"
                />
                <!-- LEISTE-1: Der Kopf „Alle Gespräche“ entfällt (der Befund
                     zählte ihn als dritte Zeile derselben Aussage); die zwei
                     Einstiege hängen am Plus im Handy-Kopf und stehen am
                     Desktop hier in der Liste. -->
                <ChatListe
                  v-else
                  :gruppen="gruppen"
                  :aktiv="kennung"
                  :ungelesen="ungelesen"
                  :kopf="false"
                  :neue-runde="!istHandyLage"
                  @neue-runde="rundeDialogOeffnen"
                />
              </template>
            </template>
          </template>
        </div>

        <!-- ── Verlauf ────────────────────────────────────────────────── -->
        <div class="dk-chat-verlauf-spalte" :class="{ 'nur-handy-aus': !offeneKennung || sucheOffen }">
          <!-- Leerzustand der rechten Seite (Desktop, kein Gespräch offen). -->
          <div v-if="!offeneKennung" class="dk-chat-nichts">
            <DkEmpty
              icon="💬"
              :title="sucheOffen ? 'Personen suchen' : 'Wähle ein Gespräch'"
              :text="sucheOffen
                ? 'Links findest du Personen. Ein vorhandenes Gespräch öffnet sich direkt, sonst führt der Treffer ins Profil.'
                : 'Links stehen deine Gespräche — Gruppen und Untergruppen mit Chat sowie deine Direktgespräche.'"
            >
              <template #aktion>
                <!-- HAUPTKNOPF (27.11.): gefüllt nur, solange links KEINE Liste mit
                     eigenem „Neue Nachricht“-Hauptknopf steht — höchstens einer je Ansicht. -->
                <DkButton v-if="!sucheOffen" :variant="gruppen.length ? 'secondary' : 'primary'" as="a" :href="SUCHE">{{ NEUE_NACHRICHT }}</DkButton>
                <DkButton
                  v-if="!sucheOffen"
                  variant="secondary"
                  @click="rundeDialogOeffnen"
                >{{ NEUE_RUNDE }}</DkButton>
              </template>
            </DkEmpty>
          </div>

          <div v-else class="dk-chat-verlauf">
            <!-- Kopf des offenen Gesprächs: zurück (nur Handy), Titel, Zähler.
                 Am Handy führt „zurück“ in die Liste zurück; überdeckt die
                 Suche das Gespräch (einspaltig), ist sie der Weg zu ihr
                 (CHAT-3c-2, SOLL 4). Ein normaler Link.

                 CHAT-3a-4 (SOLL 3): Der Stumm-Schalter sitzt HIER als
                 Symbolknopf mit aria-label — am Handy steht er damit im EINEN
                 sichtbaren Kopf (der Seitenkopf ist dort ausgeblendet), am
                 Desktop trug ihn vorher der Seitenkopf.

                 CHAT-7b-UI (Karte Punkt 3): In einer RUNDE trägt der Kopf
                 zusätzlich „Person vorschlagen“ und „Runde verlassen“ und
                 eine aufklappbare Liste der Teilnehmenden. -->
            <div class="dk-chat-verlauf-kopf">
              <a class="dk-chat-zurueck" :href="zurueckZiel" aria-label="Zurück zur Liste">
                <span aria-hidden="true">‹</span>
              </a>
              <div class="dk-chat-verlauf-titel">
                <h2>{{ titel }}</h2>
                <p v-if="unterKopf" class="dk-chat-verlauf-unter">
                  <span v-if="kontoText">{{ kontoText }}</span>
                  <span v-if="offenesGespraech && offenesGespraech.stumm" class="dk-chat-stumm-hinweis">
                    <template v-if="kontoText"> · </template>stumm geschaltet
                  </span>
                </p>
                <!-- CHAT-7b-UI: die Beteiligten einer Runde — aufklappbar, damit
                     der Kopf schmal bleibt und die Zahl schon dasteht. -->
                <template v-if="istOffeneRunde && rundenMitglieder.length">
                  <DkButton
                    variant="ghost"
                    size="sm"
                    class="dk-chat-textknopf dk-runde-teilnehmer-knopf"
                    :aria-expanded="teilnehmerOffen ? 'true' : 'false'"
                    :aria-controls="RUNDE_TEILNEHMER_ID"
                    @click="teilnehmerOffen = !teilnehmerOffen"
                  >Teilnehmende</DkButton>
                  <ul v-show="teilnehmerOffen" :id="RUNDE_TEILNEHMER_ID" class="dk-runde-teilnehmer">
                    <!-- Namen aus der Serverantwort — nie eine rohe Kennung. -->
                    <li v-for="person in rundenMitglieder" :key="person.mitglied">
                      <span class="dk-runde-teilnehmer-name">{{ person.name }}</span>
                    </li>
                  </ul>
                </template>
              </div>
              <!-- CHAT-7b-UI-b (Karte Punkt 1): „Nicht mehr anschreiben lassen“
                   im 1:1-Gesprächskopf. Am Desktop stehen die Aktionen hinter
                   dem vorhandenen „⋯“-Muster (`DkAktionen`, UX2e); am Handy ist
                   es derselbe Knopf — er sitzt in DIESEM einen sichtbaren Kopf.
                   Nur im 1:1 und nur, wenn der Server den Anzeigenamen geliefert
                   hat (ohne Namen wäre die Rückfrage ein Satz über „diese
                   Person“ zu einer Person, die eine Zeile darüber steht). -->
              <DkAktionen
                v-if="sperrAktionSichtbar"
                :eintraege="sperrEintraege"
                :label="`Aktionen für ${titel}`"
                :menue-label="`Aktionen für ${titel}`"
                kennung="chat-gespraech"
              />
              <!-- CHAT-7b-UI (Karte Punkt 3): die beiden Runden-Aktionen.
                   „Person vorschlagen“ nur, solange die Runde unter 8 steht
                   (`darfVorschlagen` — eine Zahl aus der Serverantwort, keine
                   eigene Rechtelogik).
                   Am HANDY stehen sie im „⋯“-Muster (`DkAktionen`, Review R1
                   Punkt 9) — sonst liefe der Kopf bei 360 px über; am Desktop
                   bleiben es zwei Knöpfe. -->
              <template v-if="istOffeneRunde && !istPlatzhalter">
                <template v-if="!istHandyLage">
                  <DkButton
                    v-if="vorschlagenMoeglich"
                    variant="secondary"
                    size="sm"
                    class="dk-chat-kopf-knopf"
                    :disabled="verlassenLaeuft"
                    @click="vorschlagDialogOeffnen"
                  >{{ VORSCHLAG_KNOPF }}</DkButton>
                  <DkButton
                    variant="ghost"
                    size="sm"
                    class="dk-chat-kopf-knopf"
                    :loading="verlassenLaeuft"
                    @click="rundeVerlassen"
                  >{{ VERLASSEN_KNOPF }}</DkButton>
                </template>
                <DkAktionen
                  v-else
                  :eintraege="rundenEintraege"
                  :label="`Aktionen für ${titel}`"
                  :menue-label="`Aktionen für ${titel}`"
                  kennung="chat-runde"
                />
              </template>
              <DkButton
                v-if="offenesGespraech && !istPlatzhalter"
                variant="ghost"
                size="sm"
                class="dk-chat-suche-knopf"
                :aria-expanded="gespraechSucheOffen ? 'true' : 'false'"
                aria-label="Im Gespräch suchen"
                title="Im Gespräch suchen"
                @click="gespraechSucheUmschalten"
              ><template #icon><span aria-hidden="true">⌕</span></template></DkButton>
              <DkButton
                v-if="offenesGespraech && !istPlatzhalter"
                variant="ghost"
                size="sm"
                class="dk-chat-stumm-knopf"
                :aria-pressed="offenesGespraech.stumm ? 'true' : 'false'"
                aria-label="Stumm"
                :title="offenesGespraech.stumm ? 'Stummschaltung aufheben' : 'Stumm schalten'"
                @click="stummUmschalten"
              ><template #icon><span aria-hidden="true">{{ offenesGespraech.stumm ? '🔕' : '🔔' }}</span></template></DkButton>
            </div>

            <!-- CHAT-11b: Suche IM Gespräch (Karte Punkt 3). Sie steht unter dem
                 Kopf: Feld, Trefferliste, Weitere-Treffer. Escape schließt. -->
            <div v-if="gespraechSucheOffen" class="dk-chat-gespraechsuche">
              <div class="dk-chat-gespraechsuche-feld">
                <label class="dk-chat-nur-vorlesen" for="chat-gespraech-suche">{{ GESPRAECH_PLATZHALTER }}</label>
                <input
                  id="chat-gespraech-suche"
                  ref="gespraechSuchFeld"
                  class="dk-chat-gespraechsuche-input"
                  type="search"
                  autocomplete="off"
                  :value="gespraechSucheBegriff"
                  :placeholder="GESPRAECH_PLATZHALTER"
                  aria-haspopup="listbox"
                  :aria-expanded="gespraechTreffer.length ? 'true' : 'false'"
                  :aria-controls="gespraechTreffer.length ? GESPRAECH_TREFFER_LISTE : null"
                  :aria-activedescendant="gespraechTreffer.length ? trefferOption(GESPRAECH_TREFFER_LISTE, gespraechTrefferAktiv) : null"
                  @input="gespraechSucheTippen($event.target.value)"
                  @keydown="gespraechTrefferTaste"
                />
                <DkButton
                  variant="ghost"
                  size="md"
                  class="dk-chat-suchweg"
                  aria-label="Suche im Gespräch schließen"
                  @click="gespraechTrefferSchliessen"
                >
                  <span aria-hidden="true">✕</span>
                </DkButton>
              </div>
              <p class="dk-treffer-ansage" aria-live="polite">{{ trefferAnsage({
                anzahl: gespraechTreffer.length, laedt: gespraechSucheLaedt, fehler: gespraechSucheFehler,
              }) }}</p>
              <p v-if="gespraechSucheFehler" class="dk-chat-fehler" role="alert">{{ gespraechSucheFehler }}</p>
              <DkSkelett v-else-if="gespraechSucheLaedt" form="zeilen" :anzahl="2" />
              <p
                v-else-if="gespraechSucheBegriff.trim().length >= 2 && !gespraechTreffer.length"
                class="dk-chat-hinweis"
              >{{ KEINE_TREFFER_TEXT }}</p>
              <ul
                v-if="gespraechTreffer.length"
                :id="GESPRAECH_TREFFER_LISTE"
                class="dk-chat-gespraechsuche-liste"
                role="listbox"
                aria-label="Treffer in diesem Gespräch"
              >
                <li
                  v-for="(zeile, i) in gespraechTreffer"
                  :id="trefferOption(GESPRAECH_TREFFER_LISTE, i)"
                  :key="zeile.nachricht"
                  :data-name="zeile.nachricht"
                  class="dk-chat-gespraechsuche-zeile"
                  :class="{ 'is-aktiv': i === gespraechTrefferAktiv }"
                  role="option"
                  :aria-selected="i === gespraechTrefferAktiv ? 'true' : 'false'"
                  @click="gespraechTrefferWaehlen(zeile)"
                >
                  <span class="dk-chat-gespraechsuche-kopf">
                    <span class="dk-chat-gespraechsuche-absender">{{ zeile.absender || 'Unbekannt' }}</span>
                    <span class="dk-chat-gespraechsuche-zeit">{{ zeile.zeit }}</span>
                  </span>
                  <!-- Ausschnitt: drei Teile, der Treffer hervorgehoben — nur
                       Text in Klammern (ein „<script>“ bleibt sichtbarer
                       Text, wird nie als HTML eingesetzt). -->
                  <span class="dk-chat-gespraechsuche-ausschnitt"><span>{{ zeile.teile.vor }}</span><mark v-if="zeile.teile.treffer">{{ zeile.teile.treffer }}</mark><span>{{ zeile.teile.nach }}</span></span>
                </li>
              </ul>
              <DkButton
                v-if="gespraechSucheMehr"
                variant="ghost"
                size="sm"
                class="dk-chat-textknopf"
                @click="gespraechMehrHolen"
              >Weitere Treffer</DkButton>
            </div>

            <!-- CHAT-7b-UI-b (Karte Punkt 1): der ruhige Hinweis nach dem
                 Sperren (`role="status"`, keine Alarmfarbe — eine Auskunft). -->
            <p v-if="sperrErfolgText" class="dk-chat-hinweis" role="status">{{ sperrErfolgText }}</p>
            <!-- CHAT-11b: „Diese Nachricht gibt es nicht mehr.“ — ruhig, nach
                 einem Sprung auf eine gelöschte Nachricht (role="status"). -->
            <p v-if="sprungHinweis" class="dk-chat-hinweis dk-chat-sprungweg" role="status">{{ sprungHinweis }}</p>
            <!-- Review R1 Punkt 8: Fehler beim Verlassen stehen AM KOPF als
                 ruhiger Hinweis (role="status") — der gelesene Verlauf bleibt
                 stehen, `verlaufFehler` würde ihn ersetzen. -->
            <p v-if="verlassenFehler" class="dk-chat-hinweis" role="status">{{ verlassenFehler }}</p>

            <p v-if="verlaufFehler" class="dk-chat-fehler" role="alert">{{ verlaufFehler }}</p>
            <p v-else-if="verlaufHinweis || listeHinweis" class="dk-chat-hinweis">
              {{ verlaufHinweis || listeHinweis }}
            </p>

            <!-- Der Verlauf: role="log" + aria-live="polite" (Karte Punkt 5).
                 Nachladen nach oben beim Scrollen an den Anfang. -->
            <div
              ref="verlaufEl"
              class="dk-chat-nachrichten"
              role="log"
              aria-live="polite"
              aria-relevant="additions"
              :aria-label="`Verlauf von ${titel}`"
              tabindex="-1"
              @scroll.passive="beimScrollen"
            >
              <!-- CHAT-7b-UI (Karte Punkt 5): wer neu dazugekommen ist, sieht
                   den Verlauf erst ab dem Eintritt — der Server sagt es
                   (`ab_eintritt`); ohne das Feld steht hier nichts. -->
              <p v-if="eintrittHinweis" class="dk-chat-hinweis dk-chat-eintritt" role="status">
                {{ eintrittHinweis }}
              </p>
              <DkSkelett v-if="aelterLaedt" form="zeilen" :anzahl="2" />
              <DkButton
                v-else-if="aelterMoeglich"
                variant="ghost"
                size="sm"
                class="dk-chat-textknopf"
                @click="aeltereLaden"
              >Ältere Nachrichten laden</DkButton>

              <DkSkelett v-if="verlaufLaedt && !nachrichten.length" form="zeilen" :anzahl="4" text="Verlauf wird geladen …" />
              <DkEmpty
                v-else-if="!nachrichten.length"
                icon="💬"
                :title="VERLAUF_LEER.titel"
                :text="VERLAUF_LEER.text"
              />
              <!-- Die Zeilen stehen in einer LISTE innerhalb der Log-Region:
                   `role="log"` trägt keine <li>, die brauchen ein <ul>. -->
              <ul v-else class="dk-chat-verlaufsliste">
                <template v-for="(n, i) in nachrichtenMitTag" :key="n.ident">
                  <li v-if="n.tag" class="dk-chat-tag"><span>{{ n.tag }}</span></li>
                  <!-- CHAT-N3: Die Handy-Lage fragt die SEITE einmal, die
                       Blase bekommt sie als Prop — nicht 200 Beobachter für
                       200 Nachrichten.

                       CHAT-7b-UI (Karte Punkt 4): Eine Vorschlags-Systemzeile
                       ist KEIN Beitrag — sie hat weder Bearbeiten/Löschen/
                       Melden noch Antworten. Sie wird als eigene Zeile
                       gezeichnet (`ChatVorschlagZeile`), noch VOR der Blase. -->
                  <ChatVorschlagZeile
                    v-if="istVorschlagZeile(n)"
                    :zeile="n"
                    :laeuft="vorschlagLaeuft === n.system?.vorschlag"
                    :fehler="vorschlagFehler[n.system?.vorschlag] || ''"
                    @zustimmen="vorschlagZustimmen"
                    @ablehnen="vorschlagAblehnen"
                  />
                  <ChatBlase
                    v-else
                    :nachricht="n"
                    :direkt="istOffenesDirekt"
                    :folge-start="folgeStart(i)"
                    :handy-lage="istHandyLage"
                    :ich="ich"
                    :basis="anhangBasis"
                    :class="{ 'dk-chat-sprungziel': markierteNachricht === n.ident }"
                    @reaktion="reaktionSetzen"
                    @antworten="antworten"
                    @bearbeiten="bearbeitenOeffnen"
                    @loeschen="loeschen"
                    @melden="meldenOeffnen"
                  >
                    <!-- CHAT-5-UI: Umfrage-Nachricht → Karte statt Blase. -->
                    <template v-if="n.umfrage" #karte>
                      <ChatUmfrage
                        :umfrage="n.umfrage"
                        :laeuft="umfrageLaeuft === n.umfrage.name"
                        :schliesst="umfrageSchliessenLaeuft === n.umfrage.name"
                        :fehler="umfrageFehler[n.umfrage.name] || ''"
                        @abstimmen="umfrageAbstimmen"
                        @schliessen="umfrageSchliessen"
                      />
                    </template>
                  </ChatBlase>
                </template>
              </ul>
            </div>

            <!-- Eingabe: Enter sendet, Shift+Enter macht einen Absatz.
                 CHAT-3a-4 (MUSS 1): Sie ist der feste Fuß des Verlaufs —
                 eigener Scrollkasten darüber, diese Zeile bleibt stehen. Am
                 Handy sitzt sie direkt über der unteren Leiste (safe-area).
                 CHAT-7a (Karte Punkt 3): Ist Senden nicht erlaubt (Server 403
                 / Gegenüber ausgetreten), weicht die Eingabe einem ruhigen
                 Hinweis — der Verlauf darüber bleibt lesbar. -->
            <div v-if="!darfSenden" class="dk-chat-eingabe dk-chat-gesperrt" role="status">
              <p class="dk-chat-gesperrt-titel">{{ NICHT_ERREICHBAR.titel }}</p>
              <p class="dk-chat-gesperrt-text">{{ NICHT_ERREICHBAR.text }}</p>
              <!-- CHAT-7b-UI-b (Karte Punkt 2): NUR die sperrende Seite erfährt
                   hier, dass SIE gesperrt hat — der Hinweis darüber ist
                   absichtlich derselbe wie bei jeder anderen Ursache
                   („nicht erreichbar“), damit die Sperre sich nicht verrät.
                   Aufgehoben wird in den Einstellungen (ein Weg, eine Stelle). -->
              <p v-if="eigeneSperre" class="dk-chat-gesperrt-text">
                {{ eigeneSperre.text }}
                <a :href="eigeneSperre.href">{{ eigeneSperre.linkText }}</a>
              </p>
            </div>
            <form v-else id="chat-eingabe-form" class="dk-chat-eingabe" @submit.prevent="senden">
              <p v-if="antwortAuf" class="dk-chat-antwortzeile">
                <span class="dk-chat-antwort-text">Antwort auf: {{ antwortAuf.antwortText || antwortAuf.text || 'eine Nachricht' }}</span>
                <DkButton variant="ghost" size="sm" class="dk-chat-textknopf" @click="antwortAuf = null">Antwort verwerfen</DkButton>
              </p>
              <!-- CHAT-12b: die Anhänge, die auf das Senden warten — je Datei
                   ein Chip mit Name, Größe, Stand und Entfernen-Knopf. Sie
                   stehen ÜBER dem Feld, damit die Eingabezeile ihre Höhe
                   behält. -->
              <ChatAnhangChips :liste="anhaenge" @entfernen="anhangEntfernen" />
              <p v-if="anhangHinweis" class="dk-chat-fehler" role="alert">{{ anhangHinweis }}</p>
              <div class="dk-chat-eingabe-zeile">
                <label class="dk-chat-nur-vorlesen" for="chat-eingabe">Nachricht schreiben</label>
                <!-- CHAT-12b: „Datei anhängen“ — die Büroklammer öffnet die
                     Dateiauswahl des Systems. „accept“ bietet auch die Kamera
                     an („image/*“); geprüft wird der Typ erst im Server (an
                     den ersten Bytes), hier ist es nur eine Vorauswahl.
                     „multiple“, weil bis zu drei Anhänge je Nachricht gehen. -->
                <DkButton
                  variant="secondary"
                  size="sm"
                  class="dk-chat-anhang-knopf"
                  :aria-label="ANHANG_TEXTE.anhaengen"
                  :title="ANHANG_TEXTE.anhaengen"
                  @click="dateiWaehlen"
                ><template #icon><DkSymbol name="klammer" :groesse="16" /></template></DkButton>
                <input
                  ref="dateiFeld"
                  type="file"
                  class="dk-chat-nur-vorlesen"
                  :accept="ANHANG_ACCEPT"
                  multiple
                  tabindex="-1"
                  aria-hidden="true"
                  @change="dateienGewaehlt"
                >
                <!-- CHAT-5-UI: Umfrage starten — neben dem Senden, als
                     DkButton. Steht nur, wenn das Senden selbst möglich ist
                     (`darfSenden`, dieselbe Quelle wie das Eingabefeld). -->
                <DkButton
                  v-if="darfSenden"
                  variant="secondary"
                  size="sm"
                  @click="umfrageDialog = true"
                >{{ UMFRAGE_TEXTE.neu }}</DkButton>
                <!-- CHAT-9b: „@“ öffnet die Auswahl der Beteiligten. Die
                     Listen-Eigenschaften hängen am EINGABEFELD (dort steht
                     der Fokus, dort wird getippt); die Liste selbst steht
                     darüber und zeigt nur die gefilterten Treffer.
                     R1/4: `aria-expanded`/`aria-controls`/`aria-activedescendant`
                     hängen an `auswahlSichtbar` — ohne Treffer steht keine
                     Liste im DOM, dann darf der Vorleser auch keine sehen.
                     R1/5: kein `aria-label` mehr am Feld (es gibt das
                     `<label for>`), dafür eine höfliche Ansage der Trefferzahl.
                     CHAT-9b-2 (Entscheidung Operator): KEIN `role="combobox"`
                     am `<textarea>` — AXE verlangt dafür ein Eingabefeld der
                     Combobox-Bauart, ein mehrzeiliges Feld ist es nicht. Die
                     Beziehung Feld→Liste steht als `aria-haspopup="listbox"` +
                     `aria-controls` + `aria-activedescendant`; `type="text"`
                     trägt jeder Vorleser auch ohne Rolle. -->
                <textarea
                  id="chat-eingabe"
                  ref="eingabeEl"
                  v-model="text"
                  class="dk-chat-feld"
                  rows="1"
                  :placeholder="eingabeHinweis"
                  :maxlength="NACHRICHT_MAX"
                  aria-haspopup="listbox"
                  :aria-expanded="auswahlSichtbar ? 'true' : 'false'"
                  :aria-controls="auswahlSichtbar ? ERWAEHNUNG_LISTE : null"
                  :aria-activedescendant="auswahlSichtbar ? optionKennung(ERWAEHNUNG_LISTE, erwaehnungAktiv) : null"
                  aria-autocomplete="list"
                  @keydown="beimTasten"
                  @input="erwaehnungGetippt"
                  @click="erwaehnungPruefen"
                  @keyup="erwaehnungPruefenNachTaste"
                ></textarea>
                <DkButton
                  type="submit"
                  variant="primary"
                  :loading="sendet"
                  :disabled="!darfSendenJetzt"
                  :title="sendenSperrgrund"
                >
                  {{ SENDEN_TEXT }}
                </DkButton>
                <!-- R1/3: `offen` ist das OFFENE „@“ (nicht `auswahlSichtbar`):
                     bei 0 Treffern steht kein `listbox` da, aber der
                     „weiter tippen“-Hinweis schon — er ist ein `<p>`
                     außerhalb der Liste. -->
                <ChatErwaehnung
                  :beteiligte="erwaehnungTreffer"
                  :offen="erwaehnungOffen"
                  :aktiv="erwaehnungAktiv"
                  :listen-kennung="ERWAEHNUNG_LISTE"
                  :mehr="erwaehnungMehr"
                  @waehlen="erwaehnungWaehlen"
                />
                <!-- R1/5: Die Trefferzahl wird angesagt, ohne den Fokus zu
                     stehlen (höflich, nur bei sichtbarer Liste). -->
                <p class="dk-chat-nur-vorlesen" aria-live="polite">{{ auswahlAnsage }}</p>
              </div>
              <p v-if="eingabeFehler" class="dk-chat-fehler" role="alert">{{ eingabeFehler }}</p>
            </form>
          </div>
        </div>
      </div>
    </template>

    <!-- CHAT-5-UI: „Umfrage starten“ — Frage, Antworten, anonym/offen, Frist. -->
    <ChatUmfrageDialog
      v-model="umfrageDialog"
      :laeuft="umfrageAnlegenLaeuft"
      :fehler="umfrageAnlegenFehler"
      :darf-senden="darfSenden"
      @anlegen="umfrageAnlegen"
    />

    <!-- CHAT-7b-UI: „Neue Runde“ — Name und 2–7 Personen aus der einen
         Personensuche (Karte Punkt 1). -->
    <ChatRundeDialog
      v-model="rundeDialogOffen"
      :laeuft="rundeAnlegenLaeuft"
      :fehler="rundeAnlegenFehler"
      @anlegen="rundeAnlegen"
    />

    <!-- CHAT-7b-UI: „Person vorschlagen“ — dieselbe Suche, EINE Person, mit
         Zustimmung der Runde (Karte Punkt 3). -->
    <DkDialog
      :model-value="vorschlagDialogOffen"
      :title="VORSCHLAG_KNOPF"
      @close="vorschlagDialogOffen = false"
    >
      <div class="dk-runde-vorschlag">
        <p class="dk-runde-hinweis">
          Vorgeschlagen wird <strong>eine</strong> Person. Aufgenommen wird sie, wenn alle
          anderen Beteiligten zustimmen.
        </p>
        <RundePersonenAuswahl
          :mehrfach="false"
          :laeuft="vorschlagAnlegenLaeuft"
          :ohne="vorschlagOhneListe"
          feld-id="runde-personensuche"
          feld-label="Person"
          @waehlen="vorschlagSenden"
        />
        <p v-if="vorschlagAnlegenFehler" class="dk-runde-fehler" role="alert">
          {{ vorschlagAnlegenFehler }}
        </p>
      </div>
    </DkDialog>

    <!-- CHAT-6-UI: „Melden“ — Grundauswahl, Freitext (≤ 500), der Hinweis
         „Wer Meldungen prüft, sieht diese Nachricht und die fünf davor.“ IMMER
         sichtbar vor dem Absenden. Der Dialog sendet nicht selbst; die Seite
         ruft `chat.meldung_senden` und gibt die Antwort zurück. -->
    <ChatMeldungDialog
      v-model="meldeDialog"
      :laeuft="meldeLaeuft"
      :fehler="meldeFehler"
      :eingegangen="meldeEingegangen"
      @melden="meldungSenden"
    />

    <!-- Bearbeiten-Fenster: eigener Text, 15 Minuten (Server prüft erneut). -->
    <DkDialog
      :model-value="Boolean(bearbeiten)"
      title="Nachricht bearbeiten"
      @close="bearbeiten = null"
    >
      <label class="dk-chat-nur-vorlesen" for="chat-bearbeiten">Nachricht bearbeiten</label>
      <textarea
        id="chat-bearbeiten"
        v-model="bearbeitenText"
        class="dk-chat-feld dk-chat-feld-gross"
        rows="4"
        :maxlength="NACHRICHT_MAX"
      ></textarea>
      <p v-if="bearbeitenFehler" class="dk-chat-fehler" role="alert">{{ bearbeitenFehler }}</p>
      <template #footer>
        <DkButton variant="ghost" @click="bearbeiten = null">Abbrechen</DkButton>
        <DkButton variant="primary" :loading="bearbeitenLaeuft" @click="bearbeitenSpeichern">Speichern</DkButton>
      </template>
    </DkDialog>
  </div>
</template>

<script setup>
/**
 * Nachrichten — der Bereich „Nachrichten“ (CHAT-3a).
 *
 * Grundlagen: `docs/konzepte/CHAT-KONZEPT.md` 1 (S1), 6.2 (Variante B),
 * 9 (F1–F11 — Lesestand nur als Summe, Stumm je Person, Untergruppe eigener
 * Raum), 10.1–10.3. Entwürfe `chat-entwurf/B-desktop.html` / `B-handy.html`,
 * aber mit dem BESTEHENDEN Design-System (DkCard, DkBadge, DkButton, Tokens) —
 * keine neuen Farben, Ausgrauung über `--subtle`/`--surface-2`.
 *
 * WAS HIER STEHT UND WAS NICHT
 * Die Regeln (Gruppierung, Zeitformate, Nachladen, Polling, Zähler) liegen in
 * `composables/nachrichtenLogik.mjs` und `composables/nachrichtenReaktionen.mjs`
 * — ohne DOM prüfbar (`tests/chat3a-nachrichten.test.mjs`). Diese Seite holt,
 * zeichnet und verdrahtet.
 *
 * SERVER (`backend/src/diakronos_app/api/chat.py`):
 *   GET  chat.meine_gespraeche                 → {gespraeche: [...]}
 *   GET  chat.verlauf(gespraech, vor)          → {nachrichten, vor, seit}
 *   POST chat.gespraech_anlegen(gruppe?, untergruppe?)
 *   POST chat.senden(gespraech, text, antwort_auf)
 *   POST chat.aendern(nachricht, text)
 *   POST chat.loeschen(nachricht)
 *   POST chat.reaktion_setzen(nachricht, reaktion)
 *   POST chat.lesestand_setzen(gespraech, nachricht?)
 *   POST chat.stumm_setzen(gespraech, an)
 *   GET  chat.personen_suchen(q, limit)        → {treffer, limit}  (CHAT-7a)
 *
 * CHAT-7a: Direktgespräche (1:1) laufen in DERSELBEN Liste und demselben
 * Verlauf; „Neue Nachricht“ führt in die Personensuche
 * (`#/nachrichten/suche`). Angelegt wird ein 1:1 ausschließlich am Profil über
 * `chat.direkt_oeffnen` — diese Seite legt nichts an.
 *
 * NICHT in dieser Karte: der Chat-Reiter in der Gruppe (CHAT-3b), Melden
 * (CHAT-6), Umfragen, Anhänge, der Umzug der Personenverwaltung.
 */
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { apiCall, apiGet, apiAntwortPruefen, apiUrl } from '../composables/useApi.js'
import { useSession } from '../composables/useSession.js'
// CHAT-11b: Der Sprung zu einer Nachricht öffnet das Gespräch über die
// ADRESSE (dieselbe, die auch ein Klick auf die Liste setzt) — dafür gibt es
// eine Stelle im Router.
import { navigate } from '../router.js'
import { useLadeSkelett } from '../composables/useLadeSkelett.js'
// CHAT-3a-4 (SOLL 3): Am Handy mit offenem Gespräch gibt es nur EINEN Kopf
// (den Verlaufskopf) — dieselbe Handy-Lage wie das Gerüst (`--layout-mobil`,
// Klasse `.dk-app--handy`), keine zweite Breakpoint-Kopie.
import { useHandyLage } from '../composables/handyLage.mjs'
import { bestaetigen } from '../composables/useBestaetigen.js'
import { modulChatErlaubt } from '../modulRechte.mjs'
import { fehlertext } from '../../shared/fehlertexte.js'
import {
  BEREICH, LISTE_LEER, MODUL_AUS, NACHRICHT_MAX, SENDEN_TEXT, TAKT_MS, VERLAUF_LEER,
  aelterStand, backoffMs, eingabePlatzhalter,
  fehlerZustand, folgeStarten, fremdeNeue, gespraechAusHash, gespraechHash, gruppierteListe,
  lesestandFaellig, mitTagesmarken, pruefeText, seiteEinordnen, taktGeber, tasteImFeld,
  ungelesenSumme, verlaufsZeile, zeilenSchluessel,
} from '../composables/nachrichtenLogik.mjs'
// CHAT-11b (R1/4): `SUCH_HASH` = „ist das noch die Suche?“.
import { offenAusHash, qAusHash, suchHash, sucheOffenBei, entpreller, SUCH_HASH } from '../composables/nachrichtenSuche.mjs'
// CHAT-11b: Suche IN den Nachrichten — der Sprung zur Nachricht geht über
// DENSELBEN Weg wie die Erwähnungs-Glocke (`glockenziele.mjs`, CHAT-9b),
// die Regeln des Sprungs (Seiten nachladen, „nicht mehr da“) stehen in
// `composables/nachrichtenTreffer.mjs`.
import { nachrichtenAdresse, erwaehnungZiel } from '../composables/glockenziele.mjs'
import {
  GESPRAECH_PLATZHALTER, KEINE_TREFFER_TEXT, SPRUNG_ADRESSE_MS, WEG_TEXT,
  darfFragen as darfTrefferAntwort, darfTrefferFragen, frageParameter, laufNummer,
  sprungSchritt, sprungAnker, sprungZiel, trefferAnsage, trefferAusAntwort, trefferTaste,
  seiteAnhaengen, naechsteTrefferStelle, optionKennung as trefferOption,
} from '../composables/nachrichtenTreffer.mjs'
// CHAT-11b: Was an den Server geht, faltet NICHT — der Server stammt selbst
// (`frageParameter` in `nachrichtenTreffer.mjs`). Die Faltung aus
// `nachrichtenSuche.mjs` gilt nur dem Vergleich im Browser.
import { naechsteReaktion } from '../composables/nachrichtenReaktionen.mjs'
import {
  NICHT_ERREICHBAR, NEUE_NACHRICHT, SPERR_AKTION, SUCHE, direktTitel, istDirekt, istGesperrt,
  sendbar, sendeFehlerZustand, sperrBestaetigung, sperrErfolg, sperrHinweis, sperrListe,
  sperrName, verlaufUnterzeile,
} from '../composables/nachrichtenDirekt.mjs'
import DkCard from '../components/ui/DkCard.vue'
import DkAktionen from '../components/ui/DkAktionen.vue'
import DkButton from '../components/ui/DkButton.vue'
import DkSymbol from '../components/ui/DkSymbol.vue'
import DkDialog from '../components/ui/DkDialog.vue'
import DkEmpty from '../components/ui/DkEmpty.vue'
import DkSkelett from '../components/ui/DkSkelett.vue'
import ChatListe from '../components/chat/ChatListe.vue'
// LEISTE-1: die Glocke der App (derselbe Baustein wie in Kopfzeile und
// Seitenleiste) und der Name des Menue-Knopfs.
import Glocke from '../components/Glocke.vue'
import MenueKnopf from '../components/MenueKnopf.vue'
import ChatBlase from '../components/chat/ChatBlase.vue'
// CHAT-12b: Anhänge — die Regeln in `anhaenge.mjs`, gezeichnet in zwei
// Bausteinen (Chips über der Eingabe, Anhänge in der Blase).
import ChatAnhangChips from '../components/chat/ChatAnhangChips.vue'
import {
  ANHANG_ACCEPT, ANHAENGE_MAX, TEXTE as ANHANG_TEXTE,
  anhangKennungen, anhangAntwortGilt, anhangMaxBytes, auswahlPruefen,
  chipAendern, chipBauen, chipEntfernen,
  darfSenden as darfSendenMitAnhang, laedtNoch, sendeRumpf,
  uploadAntwort, uploadFehlerText, uploadLauf,
} from '../components/chat/anhaenge.mjs'
import ChatSuche from '../components/chat/ChatSuche.vue'
import ChatUmfrage from '../components/chat/ChatUmfrage.vue'
import ChatUmfrageDialog from '../components/chat/ChatUmfrageDialog.vue'
import ChatMeldungDialog from '../components/chat/ChatMeldungDialog.vue'
import ChatRundeDialog from '../components/chat/ChatRundeDialog.vue'
import ChatVorschlagZeile from '../components/chat/ChatVorschlagZeile.vue'
import RundePersonenAuswahl from '../components/chat/RundePersonenAuswahl.vue'
import ChatErwaehnung from '../components/chat/ChatErwaehnung.vue'
// CHAT-9b: Erwähnungen — die Regeln (Auswahl, Bereinigung vor dem Senden,
// Hervorhebung in der Blase) stehen DOM-frei in `components/chat/erwaehnung.mjs`.
import {
  antwortSchluessel, auswahlAnzahl, auswahlBereinigen, auswahlTaste, einsetzen, erwaehnungAntwort,
  erwaehnungFrage, erwaehnungSchluessel, erwaehnungSchluesselTeile,
  ERWAEHNUNG_ANZAHL, ERWAEHNUNG_ENTPRELLUNG_MS,
  istEingabemethode, naechsteStelle, nurAuswahlTaste, offeneErwaehnung, optionKennung,
  vorschlaege,
} from '../components/chat/erwaehnung.mjs'
import { TEXTE as UMFRAGE_TEXTE, istUmfrageZeile } from '../components/chat/umfrage.mjs'
import {
  NEUE_RUNDE, VORSCHLAG_KNOPF, VERLASSEN_KNOPF,
  darfVorschlagen, eintrittsHinweis, istRunde, istVorschlagZeile, rundenKopf,
  rundenMitglieder as rundenMitgliederAus, rundenTitel, rundeAnlegenRumpf,
  stimmeRumpf, verlassenFrage, verlassenRumpf, vorschlagOhne, vorschlagRumpf,
} from '../composables/nachrichtenRunden.mjs'
// CHAT-6-UI: Melden — Prüfung und Auslegung der Antwort in `meldung.mjs`.
import {
  KEIN_ZUGRIFF as MELDUNG_KEIN_ZUGRIFF, meldbar as darfMelden, meldeFehlerText,
  sendeAntwort as meldeAntwort,
} from '../components/chat/meldung.mjs'

// ── LEISTE-1: Vollbild-Seite ───────────────────────────────────────────────
/**
 * Die Seite liegt im Vollbild (router.js `vollbildRoute`): es gibt keine
 * App-Kopfzeile mehr, die den Menü-Knopf trägt. Am HANDY öffnet deshalb das ☰
 * im eigenen Kopf (`.dk-chat-leiste`) die Schublade — der EINE Zustand dafür
 * gehört der App-Wurzel, hier nur das Ereignis.
 */
defineEmits(['open-menu'])

// ── Sitzung und Adresse ────────────────────────────────────────────────────

const { mitglied } = useSession()
// CHAT-3a-4: Handy-Lage (dieselbe Quelle wie das Gerüst) für den EINEN Kopf
// am Handy — und für „nicht nach unten springen, während oben gelesen wird“.
const { istHandyLage } = useHandyLage()
const boot = computed(() => (typeof window === 'undefined' ? {} : (window.__DIakonosBOOT || {})))
/** Das Modul `chat` — dieselbe Regel wie Router-Guard und Handy-Leiste. */
const modulAn = computed(() => modulChatErlaubt(boot.value))
/** „Ich“ = Mitglied-Kennung. Der Server setzt `eigene` je Nachricht; das hier
 *  ist nur der Rückfall, wenn eine Antwort das Feld nicht trägt. */
const ich = computed(() => String(mitglied.value?.name || ''))

/** Kennung aus der Adresse (`#/nachrichten/<gespraech>`) — folgt dem Router.
 *  Während einer Suche ist sie LEER (die Adresse ist dann die Suche); das
 *  Gespräch rechts kommt dann aus `&offen=` (`offeneKennung`). */
const kennung = ref(gespraechAusHash(typeof window === 'undefined' ? '' : window.location.hash))
/** CHAT-3c: Ist die Suche offen (`#/nachrichten/suche?q=…`)? Eine Suchadresse
 *  OHNE Begriff verhält sich wie die Liste (Review R1, SOLL d). */
const sucheOffen = ref(sucheOffenBei(typeof window === 'undefined' ? '' : window.location.hash))
/** Der Begriff der Suche aus der Adresse (leer = Adresse ohne `q`). */
const suchBegriff = ref(qAusHash(typeof window === 'undefined' ? '' : window.location.hash))
/** CHAT-3c-2: Das Gespräch, das am Desktop RECHTS offen bleibt, während gesucht
 *  wird — `&offen=<kennung>` der Suchadresse. Am Handy ist es unsichtbar (eine
 *  Spalte); „Zurück“ stellt es wieder her.
 *
 *  Übernommen wird es NUR, wenn die Kennung in der eigenen Gesprächsliste steht
 *  (Review R1, SOLL 5): ein Link darf nie ein `gespraech_anlegen` auslösen —
 *  und ein Ortesschlüssel (Gruppenname) ist keine Kennung. */
// Noch NICHT gegen die Liste geprüft: die entsteht weiter unten (`gespraeche`)
// — die Prüfung holt `laden()` direkt nach dem ersten Abruf nach (SOLL 5).
const offenAusAdresse = ref(offenAusHash(
  typeof window === 'undefined' ? '' : window.location.hash,
))

/** Steht diese Kennung in der eigenen Gesprächsliste? (leer, solange sie lädt) */
function istEigenesGespraech(wert) {
  const k = String(wert || '').trim()
  if (!k) return ''
  return gespraeche.value.some((e) => String(e?.name || '') === k) ? k : ''
}

/**
 * `&offen=` aus der Adresse — nur, wenn die Kennung in der eigenen
 * Gesprächsliste steht (Review R1, SOLL 5): ein Link darf nie ein
 * `gespraech_anlegen` auslösen, und ein Ortesschlüssel (Gruppenname) ist keine
 * Kennung. Vor dem Laden der Liste ist die Antwort immer leer; `laden()`
 * wiederholt die Prüfung, sobald die Liste da ist.
 */
function offenMitKennung(wert) {
  return istEigenesGespraech(wert)
}

/**
 * Die EINE Kennung der rechten Spalte (CHAT-3c-2): das offene Gespräch aus der
 * Adresse ODER das Gespräch hinter der Suche (`&offen=`). Verlauf, Titel,
 * Stumm, Takt, Senden und Lesestand hängen alle hieran — nicht an `kennung`,
 * das während einer Suche leer ist. Sonst würde schon das erste getippte
 * Zeichen das offene Gespräch leeren (Review R1, MUSS 1).
 */
const offeneKennung = computed(() => String(kennung.value || offenAusAdresse.value || ''))

function hashGeaendert() {
  const hash = typeof window === 'undefined' ? '' : window.location.hash
  // MUSS 3b: Das Feld (nicht die Adresse) bestimmt, was gesucht wird. Diese
  // Stelle liest die Adresse nur NACH (Zurück/Vorwärts, neuer Aufbau) — ein
  // laufendes Tippen schreibt nichts hierher. `sucheOffenBei` verlangt einen
  // Begriff: `#/nachrichten/suche` ohne `q` ist der Listenmodus (SOLL d).
  kennung.value = gespraechAusHash(hash)
  sucheOffen.value = sucheOffenBei(hash)
  suchBegriff.value = qAusHash(hash)
  offenAusAdresse.value = offenMitKennung(offenAusHash(hash))
}

// ── Liste ──────────────────────────────────────────────────────────────────

const gespraeche = ref([])
const listeLaedt = ref(true)
const listeFehlerRoh = ref(null)
/** Kleiner Hinweis, wenn ein TAKT-Abruf scheitert — die letzte gute Liste bleibt
 *  stehen (Review R1: kein Vollbild-Fehler für einen misslungenen Poll). */
const listeHinweis = ref('')
const { skelettSichtbar } = useLadeSkelett(listeLaedt)

/**
 * Was die Liste im Fehlerfall zeigt: 403 → „kein Zugriff“, 404 → „gibt es
 * nicht“, 417 → Satz des Servers; alles andere (Netz, 500) den Katalogtext
 * (`fehlertext`) — NIE eine leere Fläche ohne Erklärung (Prinzip I5).
 */
const listenFehler = computed(() => {
  const roh = listeFehlerRoh.value
  if (!roh) return null
  const zustand = fehlerZustand(roh)
  if (zustand) return zustand
  return { art: 'allgemein', titel: 'Die Gespräche konnten nicht geladen werden', text: fehlertext(roh) }
})
const gruppen = computed(() => gruppierteListe(gespraeche.value))
const ungelesen = computed(() => ungelesenSumme(gespraeche.value))
/** Sind wir noch da? Ein Abruf, der nach dem Abbau zurückkommt, darf nichts mehr
 *  schreiben und nichts mehr starten (Review R1, MUSS 3). */
let aktivSeite = true

/**
 * Der Eintrag des offenen Gesprächs, wenn die Liste ihn nicht kennt.
 *
 * CHAT-7a-UI-2 (Review R1, SOLL 3): `platzhalter: true` markiert ihn als
 * PLATZHALTER — die Kennung ist bekannt, alles andere (Titel, Teilnehmer,
 * Stumm) nicht. Daraus folgt: kein Stumm-Knopf (ob stumm geschaltet ist, weiß
 * niemand) und keine Unterzeile im Verlaufskopf. Sonst flackerte beim ersten
 * Laden einer Gruppe kurz Gruppen-Text im 1:1 auf.
 */
function platzhalterZeile(kennung) {
  return { name: kennung, art: '', gruppe: null, untergruppe: null, titel: '', teilnehmer: 0, platzhalter: true }
}

/** Die Zeile des offenen Gesprächs (Titel, Teilnehmer, Stumm) aus der Liste —
 *  für die EINE Kennung der rechten Spalte (`offeneKennung`), also auch für das
 *  Gespräch hinter der Suche (`&offen=`). */
const offenesGespraech = computed(() => {
  const k = offeneKennung.value
  if (!k) return null
  const gefunden = gespraeche.value.find((e) => String(e?.name || '') === k
    || zeilenSchluessel(e) === k)
  if (gefunden) return gefunden
  // CHAT-7a-UI-2: Die Liste kann (noch) fehlen — abgefragt oder gescheitert.
  // Dann bleibt der Verlauf offen und SCHREIBBAR: ob man schreiben darf,
  // entscheidet der Server (403 beim Senden), nicht das Fehlen einer Zeile in
  // einer Liste, die gar nicht geladen werden konnte. Der Eintrag trägt nur die
  // Kennung; Titel und Teilnehmerzahl bleiben leer („Unbekannte Person“ ist
  // falsch — die Kennung ist bekannt, nur der Name nicht).
  return k ? platzhalterZeile(k) : null
})
/** Ist der offene Eintrag nur ein Platzhalter (Liste kennt ihn nicht)? */
const istPlatzhalter = computed(() => offenesGespraech.value?.platzhalter === true)
/** CHAT-7b-UI: Steht hier eine RUNDE offen? (Kartenpunkte 2–5) */
const istOffeneRunde = computed(() => istRunde(offenesGespraech.value))
/**
 * CHAT-7b-UI (Karte Punkt 2): Der Titel des offenen Gesprächs. Eine bekannte
 * Kennung ohne Listeneintrag (die Liste lud nicht) heißt „Gespräch“ — „Unbekannte
 * Person“ gehört zu einem NAMENTLICHEN 1:1 aus dem Altbestand, nicht zu einer
 * fehlenden Zeile. Eine Runde trägt ihren Namen (leer → „Runde“).
 */
const titel = computed(() => {
  const eintrag = offenesGespraech.value
  if (istDirekt(eintrag)) return direktTitel(eintrag)
  if (istRunde(eintrag)) return rundenTitel(eintrag)
  return String(eintrag?.titel || '').trim() || 'Gespräch'
})
const teilnehmerZahl = computed(() => Number(offenesGespraech.value?.teilnehmer) || 0)
/** Steht das offene Gespräch in einem eigenen 1:1? (Lesestand, Unterzeile, 403) */
const istOffenesDirekt = computed(() => istDirekt(offenesGespraech.value))
/**
 * Karte UI-2 Punkt 5: die Zeile unter dem Titel. In Gruppen „N im Gespräch“,
 * im 1:1 LEER (`verlaufUnterzeile`) — kein Gruppen-Satz, keine Zählung, und
 * „gelesen“ steht dort nicht mehr (Punkt 1).
 */
const kontoText = computed(() => ((offeneKennung.value && !istPlatzhalter.value)
  ? (istOffeneRunde.value
    ? rundenKopf(offenesGespraech.value)
    : verlaufUnterzeile({ istDirekt: istOffenesDirekt.value, teilnehmer: teilnehmerZahl.value }))
  : ''))
/** Steht die Kopfzeile überhaupt da? (leer = kein `p`, keine leere Zeile).
 *  Beim Platzhalter weiß niemand, ob stumm geschaltet ist (Review R1, SOLL 3). */
const unterKopf = computed(() => Boolean(kontoText.value)
  || (!istPlatzhalter.value && Boolean(offenesGespraech.value?.stumm)))
/**
 * CHAT-7a (Karte Punkt 3, UI-2 Punkt 2): darf in dieses Gespräch geschrieben
 * werden?
 *
 * Die Antwort kommt vom SERVER — `sendenVonServerGesperrt` wird gesetzt, wenn
 * `chat.senden` mit 403 antwortet (im 1:1 heißt das: das Gegenüber ist nicht
 * mehr erreichbar). Es gibt hier KEINE eigene Rechtelogik und keine Ableitung
 * aus Anzeigefeldern: `mitglied` ist laut Backend nur Anzeige, und ein
 * Gruppen-Chat, der (noch) nicht in der Liste steht, bleibt schreibbar.
 */
const sendenVonServerGesperrt = ref(false)
const darfSenden = computed(() => sendbar(offenesGespraech.value, { gesperrt: sendenVonServerGesperrt.value }))

// ── CHAT-7b-UI-b: Kontaktsperre (Konzept S3) ────────────────────────────────
/**
 * Die EIGENE Sperrliste (`chat.meine_sperren`, GET) — der EINZIGE Ort, an dem
 * eine Sperre sichtbar ist: den Chat-Endpunkten ist „gesperrt“ nach aussen
 * nicht anzusehen (Server: derselbe Text wie „nicht erreichbar“). Sie wird
 * beim Öffnen der Seite geholt (ein Aufruf, nicht je Gespräch).
 *
 * Fehlt sie (Fehler, alter Server), bleibt sie LEER: dann gibt es keinen
 * Aufheben-Link — aber auch keine Behauptung, man habe jemanden gesperrt.
 */
const sperrStand = ref([])
/** Die Person des offenen 1:1 — die Kennung, die der Server als `mitglied`
 *  führt (`chat.kontakt_sperren` erwartet genau diesen Wert).
 *
 *  Review R1, Punkt 4: KEIN Rückfall auf `titel`. Der Titel ist ein
 *  Anzeigename, keine Kennung — bei gelöschtem Gegenüber fehlt `mitglied`,
 *  und eine Sperre auf einen Namen ginge ins Leere (oder träfe den Falschen).
 *  Ohne `mitglied` gibt es darum keine Sperr-Aktion. */
const direktMitglied = computed(() => String(offenesGespraech.value?.mitglied || '').trim())
/**
 * Aktion „Nicht mehr anschreiben lassen“ im 1:1-Kopf: nur im 1:1, nur mit
 * einem Namen (die Rückfrage nennt ihn), nur mit Kennung (der Server braucht
 * `mitglied`) — und NICHT, wenn die Person schon auf der eigenen Liste steht
 * (dann steht der Weg zum Aufheben im Hinweis unten, ein zweites „sperren“
 * wäre eine Lüge über den Zustand).
 */
const sperrAktionSichtbar = computed(() => istOffenesDirekt.value
  && !istPlatzhalter.value
  && Boolean(direktMitglied.value)
  && !istGesperrt(direktMitglied.value, sperrStand.value))
/**
 * Die Einträge des „⋯“-Menüs. `aktion` ist die FUNKTION `sperren` selbst
 * (`function` wird hochgezogen, sie steht also schon hier); eine Hülle
 * (`() => sperren()`) legt ein durchgereichtes Ereignis-Objekt als erstes
 * Argument auf `mitglied` — dann ginge der Aufruf mit dem falschen Ziel hinaus.
 */
const sperrEintraege = computed(() => [{
  key: 'sperren',
  label: SPERR_AKTION,
  icon: 'abbrechen',
  aktion: sperren,
}])
/** Der ruhige Hinweis nach dem Sperren (`role="status"`), leer = keiner. */
const sperrErfolgText = ref('')
/** Läuft der Sperr-Aufruf? (Doppelklick schickt nichts zweimal.) */
const sperrtLaeuft = ref(false)

/**
 * Der Satz unter „nicht mehr erreichbar“ — NUR für die sperrende Seite
 * (Karte Punkt 2). Er hängt an der EIGENEN Liste, nie an einer Eigenschaft des
 * Gesprächs: die gesperrte Seite sieht hier nichts Zusätzliches.
 */
const eigeneSperre = computed(() => (istOffenesDirekt.value
  && istGesperrt(direktMitglied.value, sperrStand.value) ? sperrHinweis() : null))

async function sperrListeLaden() {
  try {
    const antwort = await apiGet('chat.meine_sperren', {})
    sperrStand.value = sperrListe(antwort)
  } catch {
    // Fail closed: ohne Liste kein Aufheben-Link, keine Aussage über Sperren.
    sperrStand.value = []
  }
}

/**
 * „Nicht mehr anschreiben lassen“: erst die Rückfrage des Hauses
 * (`bestaetigen`), dann `chat.kontakt_sperren`. Danach steht die Person auf
 * der eigenen Liste — also auch der Aufheben-Weg im Hinweis unten.
 *
 * Die Sperre ist SOFORT wirksam (der Server entscheidet), aber das offene
 * Gespräch erfährt es erst beim nächsten Senden (403 → „nicht erreichbar“).
 * Beides ist gewollt: die Sperre ist keine zweite Rechtelogik im Frontend.
 */
async function sperren() {
  const mitglied = direktMitglied.value
  if (!mitglied || sperrtLaeuft.value) return
  const lage = { anzeigename: String(offenesGespraech.value?.titel || '').trim() }
  if (!(await bestaetigen(sperrBestaetigung(lage.anzeigename, mitglied)))) return
  sperrtLaeuft.value = true
  sperrErfolgText.value = ''
  try {
    await apiCall('chat.kontakt_sperren', { mitglied })
    sperrStand.value = [...sperrStand.value, { mitglied, name: sperrName(lage.anzeigename, mitglied) }]
    sperrErfolgText.value = sperrErfolg(lage.anzeigename, mitglied)
    // Die Liste (letzte Nachricht, Zähler) zieht nach — der Server führt die
    // Sperre, nicht diese Seite.
    await laden()
  } catch (fehler) {
    if (Number(fehler?.status) === 403) {
      // Der Server erlaubt diese Sperre nicht (z. B. kein Konto der Person).
      // Kein Alarm: die Aktion ist dann einfach nicht möglich.
      verlaufHinweis.value = 'Diese Person lässt sich nicht sperren.'
    } else {
      verlaufFehler.value = fehlertext(fehler)
    }
  } finally {
    sperrtLaeuft.value = false
  }
}

// ── LEISTE-1: kein Seitenkopf mehr ─────────────────────────────────────────

/**
 * Die Seite läuft im VOLLBILD (router.js, `vollbildRoute`): keine App-Kopfzeile,
 * kein Seitenkopf, kein Kartenrahmen. Titel, Unterzeile und Brotkrumen des
 * früheren Seitenkopfs entfallen damit ersatzlos (Manuel 23.11., DMB-4971:
 * „Obere Leiste mit Suche kann weg, Überschrift ‚Nachrichten‘ kann weg.“).
 * Was der Kopf leistete, steht jetzt in der Seite selbst: die Suche oben in
 * der Liste, die Glocke in Leiste und Handy-Kopf, das Gespräch im Verlaufskopf.
 */

/** Die zwei Einstiege als „⋯“-Menü im Handy-Kopf (Entwurf „02“: nur ein +). */
const neueEintraege = computed(() => [
  { text: NEUE_NACHRICHT, href: SUCHE },
  { text: NEUE_RUNDE, aktion: rundeDialogOeffnen },
])

// ── Suche (CHAT-3c) ────────────────────────────────────────────────────────

/**
 * Ziel des „zurück“-Pfeils im Verlaufskopf. Am HANDY ist das der Weg zur
 * SUCHE, wenn sie offen ist (sie ist dort die eine sichtbare Spalte, der
 * Verlauf ist ausgeblendet) — sonst die Liste. Am Desktop trägt der Pfeil
 * ohnehin nicht (er steht nur am Handy im Kopf).
 */
const zurueckZiel = computed(() => (sucheOffen.value
  ? suchHash(suchBegriff.value, offenAusAdresse.value)
  : BEREICH))

/**
 * Die Suche trägt ihren Begriff in der Adresse (`#/nachrichten/suche?q=…`).
 *
 * Review R1, MUSS 2 — der Verlauf hat GENAU EINEN Eintrag für die Suche:
 *   * Das ÖFFNEN der Suche legt ihn mit `pushState` an. Danach führt „Zurück“
 *     auf den Zustand von vorher (Liste oder offenes Gespräch) — vorher stand
 *     hier `location.replace`, das genau diesen Eintrag überschrieb und
 *     „Zurück“ aus der Suche herausführte (am Desktop sogar aus dem Verlauf).
 *   * Weitere Tastendrücke ziehen den Begriff mit `replaceState` nach — kein
 *     Eintrag je Anschlag.
 *   * Kein `hashchange` bei beidem: die Seite und die Komponente haben den
 *     Begriff schon (die Komponente meldet ihn).
 *
 * `state.liste` = „der Eintrag darunter ist die Liste“ (die Suche wurde DIREKT
 * aus der Liste geöffnet). Dann trägt die Adresse kein `&offen=`: „Feld
 * leeren“ führt auf die Liste. Kam die Suche aus einem offenen Gespräch, trägt
 * sie `&offen=<kennung>` und weiß damit, wohin „Feld leeren“ zurückführt
 * (CHAT-3c-2) — auch nach einem neuen Aufbau.
 *
 * `ersetzen` = „derselbe Eintrag“ (`replaceState`, kein `hashchange`),
 * sonst ein neuer (`pushState`). Ohne History-API springt die Adresse wie ein
 * Link.
 */
function adresseSetzen(hash, { ersetzt = true, liste = false } = {}) {
  if (typeof window === 'undefined') return
  const ziel = String(hash || BEREICH) || BEREICH
  // DIESELBE Adresse: nichts zu schreiben (kein zweiter Eintrag, kein
  // überflüssiges `hashGeaendert`).
  if (String(window.location.hash || '') === ziel) {
    if (ersetzt) return
  }
  const verlauf = window.history
  if (verlauf && typeof verlauf.replaceState === 'function') {
    // Fremden Zustand des Eintrags unberührt lassen — nur `liste` gehört uns.
    const zustand = { ...(verlauf.state || {}) }
    if (liste) zustand.liste = true
    else delete zustand.liste
    const neuerZustand = Object.keys(zustand).length ? zustand : null
    if (ersetzt) verlauf.replaceState(neuerZustand, '', ziel)
    else verlauf.pushState(neuerZustand, '', ziel)
    // Der Browser feuert bei pushState/replaceState kein `hashchange`; die
    // Adresse ist trotzdem die Wahrheit — die Seite liest sie sofort nach.
    hashGeaendert()
    return
  }
  // Ohne History-API (kein Browser): der Sprung, wie ihn ein Link täte.
  window.location.hash = ziel
}

/** Steht im aktuellen Verlaufseintrag „der Eintrag darunter ist die Liste“? */
function eintragIstListe() {
  if (typeof window === 'undefined') return true
  const zustand = window.history?.state
  if (zustand && typeof zustand === 'object' && 'liste' in zustand) return zustand.liste === true
  // Kein Zustand (fremder Eintrag, frisch geladen): dann lieber EIN Schritt zu
  // viel im Verlauf („Zurück“ führt auf die Liste) als einer zu wenig — ein
  // ersetzter Eintrag, der überschrieben wurde, ist nicht mehr erreichbar.
  // Steht in der Adresse aber ein GESPRÄCH, kann der Eintrag nicht die Liste
  // sein (er wurde von dort aus geöffnet).
  return !gespraechAusHash(typeof window === 'undefined' ? '' : window.location.hash)
}

/** Ist die Suchadresse bereits fertig? (Dann schreibt `begriffGeaendert` nichts.) */
function bereitsGesetzt(ziel) {
  return typeof window !== 'undefined' && String(window.location.hash || '') === ziel
}

/**
 * Ein Tastendruck in der Suche (oder das Leeren).
 *
 * CHAT-3c-2 (Review R1, MUSS 1): Während der Suche hängt die rechte Spalte an
 * `offeneKennung` — das offene Gespräch bleibt also stehen, egal ob die
 * Adresse es als `&offen=` trägt oder nicht. Die Adresse trägt es mit, damit
 * ein Neuladen (F5) dasselbe Bild zeigt; sie zu schreiben ist keine Bedingung
 * für das Offenbleiben.
 *
 * Leeren führt auf das Gespräch zurück, das rechts offen war (Desktop: es ist
 * sichtbar; Handy: „Zurück“ zeigt es), sonst auf die Liste. Ersetzend — ein
 * leeres Feld ist kein zweiter Schritt im Verlauf.
 */
function begriffGeaendert(begriff) {
  const begriffText = String(begriff ?? '').trim()
  if (!begriffText) {
    if (!sucheOffen.value && !suchBegriff.value && !offenAusAdresse.value) return
    // Wohin zurück? Das offene Gespräch (Desktop: es stand rechts) oder die
    // Liste. `kennung` ist der Eintrag, aus dem die Suche kam.
    const zurueck = String(kennung.value || offeneKennung.value || '')
    sucheOffen.value = false
    suchBegriff.value = ''
    offenAusAdresse.value = ''
    // Erst schreiben, dann lesen: `hashGeaendert` liest die Adresse nach.
    adresseSetzen(zurueck ? gespraechHash(zurueck) : BEREICH, { ersetzt: true })
    return
  }
  const offen = offeneKennung.value
  const ziel = suchHash(begriffText, offen)
  const schonOffen = sucheOffen.value
  sucheOffen.value = true
  suchBegriff.value = begriffText
  // Dieselbe Suchadresse: nichts zu tun (der Begriff steht schon da).
  if (bereitsGesetzt(ziel)) return
  if (!eintragIstListe()) {
    // Aus einem GESPRÄCH heraus: die Suche bekommt ihren EIGENEN Eintrag und
    // führt das Gespräch in `&offen=` mit — „Zurück“ führt ins Gespräch.
    adresseSetzen(ziel, { ersetzt: false })
    return
  }
  // Aus der Liste: EIN Eintrag für den Zustand „Suche“ — der erste Anschlag
  // hängt ihn an (`push`, `state.liste`), weitere ziehen den Begriff nach
  // (`replace`) — kein Eintrag je Anschlag.
  adresseSetzen(ziel, { ersetzt: schonOffen, liste: true })
}

/**
 * Zurück/Vorwärts: die Adresse ist die Wahrheit. `hashGeaendert` zieht Suche
 * und Gespräch nach; der `popstate`-Weg ist auf Desktop und Handy derselbe.
 */
function verlaufGeaendert() {
  hashGeaendert()
}

/**
 * Stand von Suche und offenem Gespräch — nur für den Node-Test nachlesbar
 * (`defineExpose`). Kein Betriebsweg.
 */
function sucheStand() {
  return {
    offen: sucheOffen.value,
    begriff: suchBegriff.value,
    kennung: kennung.value,
    offenGespraech: offenAusAdresse.value,
    kennungGesamt: offeneKennung.value,
  }
}

/**
 * Die Gesprächsliste holen — die EINE Abfrage von `meine_gespraeche` je Takt
 * (Review R1, MUSS 4: Liste UND Zähler kommen aus demselben Ergebnis).
 *
 * @param {{still?: boolean}} [lage] `still` = Takt/Poll: kein Ladeprotokoll,
 *        kein großer Fehler — die letzte gute Liste bleibt stehen, nur ein
 *        kleiner Hinweis erscheint.
 * @returns {Promise<boolean>} ob es geklappt hat
 */
async function laden({ still = false } = {}) {
  if (!still) {
    listeFehlerRoh.value = null
    listeHinweis.value = ''
  }
  try {
    const antwort = await apiGet('chat.meine_gespraeche')
    if (!aktivSeite) return false
    gespraeche.value = Array.isArray(antwort?.gespraeche) ? antwort.gespraeche : []
    // CHAT-12c: die eingestellte Anhangsgröße kommt in DIESER Antwort mit
    // (`anhang_max_bytes`) — kein zweiter Rundlauf. Fehlt das Feld (alter
    // Server), bleibt der Standard stehen.
    anhangGrenze.value = anhangMaxBytes(antwort)
    listeHinweis.value = ''
    // CHAT-3c-2 (Review R1, SOLL 5): `&offen=` gilt nur für ein eigenes
    // Gespräch — vor dem Laden der Liste konnte das nicht geprüft werden.
    offenAusAdresse.value = offenMitKennung(
      offenAusAdresse.value || offenAusHash(typeof window === 'undefined' ? '' : window.location.hash),
    )
    // Den Zähler der Handy-Leiste nachziehen — mit DIESER Zahl, kein zweiter
    // Aufruf: die App-Wurzel übernimmt `detail.ungelesen`.
    mitteilungSenden()
    return true
  } catch (fehler) {
    if (!aktivSeite) return false
    if (still || gespraeche.value.length) {
      // Fehlgeschlagener Poll: letzte gute Liste behalten, nur ein Hinweis.
      listeHinweis.value = 'Die Liste konnte gerade nicht aktualisiert werden.'
    } else {
      listeFehlerRoh.value = fehler
    }
    return false
  } finally {
    listeLaedt.value = false
  }
}

/**
 * Die App-Wurzel führt den Zähler der Leiste — sie bekommt die fertige SUMME
 * im Ereignis (`detail.ungelesen`) und holt sie nicht selbst noch einmal.
 *
 * MUSS 4: `summe` ist die Zahl, die mitreist. Ohne Angabe wird sie aus der
 * Liste gerechnet; `null` heißt „die Seite übernimmt, aber es gibt noch keine
 * Zahl“ — die App zeigt dann keinen Zähler und fragt NICHT nach (`fraegt`).
 * Ein `null` nur zu senden, wenn wirklich keine Liste da ist, wäre ein
 * Unterschied ohne Bedeutung: der App-Zähler unterscheidet beides nicht.
 */
function mitteilungSenden(summe = undefined) {
  if (typeof window === 'undefined' || typeof window.dispatchEvent !== 'function') return
  const zahl = summe === undefined ? ungelesenSumme(gespraeche.value) : summe
  window.dispatchEvent(new CustomEvent('dk-chat-ungelesen', {
    detail: { ungelesen: zahl, fraegt: false },
  }))
}

/**
 * Der Seite wird auf- oder abgebaut. Abgebaut gibt sie den Zähler FREI, damit
 * die App-Wurzel ihn wieder führt (sonst bliebe er für immer bei „die Seite
 * fragt“ stehen und zeigte den letzten Stand bis zum Neuladen).
 */
function mitteilungSeite(offen) {
  if (typeof window === 'undefined' || typeof window.dispatchEvent !== 'function') return
  window.dispatchEvent(new CustomEvent('dk-chat-seite', { detail: { offen: offen === true } }))
}

// ── Verlauf ────────────────────────────────────────────────────────────────

const nachrichten = ref([])
/** Das Gespräch, dessen Verlauf hier steht (`''` = keiner) — siehe `oeffnen`. */
const geoeffnet = ref('')
const verlaufLaedt = ref(false)
const verlaufFehler = ref('')
/** Kleiner Hinweis nach einem misslungenen Poll (der Verlauf bleibt stehen). */
const verlaufHinweis = ref('')
/**
 * CHAT-7b-UI (Karte Punkt 5): Steht oben im Verlauf der Eintritts-Hinweis?
 * Er kommt AUSSCHLIESSLICH aus der Antwort von `chat.verlauf` (`ab_eintritt`,
 * Regel in `nachrichtenRunden.mjs` → `eintrittsHinweis`) — fehlt das Feld,
 * steht hier nichts.
 */
const eintrittHinweisRoh = ref('')
const aelterLaedt = ref(false)
/**
 * Darf nach oben nachgeladen werden? `null` = noch KEIN Stand (frisch geöffnetes
 * Gespräch, s. `aelterStand`) — Review R1/3: vorher stand hier `false`, und das
 * Nachladen begann erst nach einem Sprung.
 */
const aelterMoeglich = ref(null)
const verlaufEl = ref(null)
const eingabeEl = ref(null)
const text = ref('')
const sendet = ref(false)
const eingabeFehler = ref('')
const antwortAuf = ref(null)
const eingabeHinweis = computed(() => eingabePlatzhalter(titel.value))
/** Höhe des Verlaufs VOR dem Nachladen — hält die Leseposition beim Nachladen. */
let scrollVorher = 0

// ── CHAT-12b: Anhänge ──────────────────────────────────────────────────────
//
// Der Ablauf (Karte Punkt 1/2): Auswahl → VORAB-Prüfung im Browser (Größe,
// Anzahl — kein Upload, wenn das schon nicht geht) → sofort hochladen, je
// Datei ein Chip → `chat.senden` nimmt die Kennungen der FERTIGEN mit.
//
// Was hier NICHT passiert: einen Anhang löschen. Ein nicht gesendeter Anhang
// räumt sich im Server selbst weg (`chat_anhaenge_aufraeumen`, 24 h) — ein
// eigener Löschaufruf wäre ein zweiter Weg mit eigenem Recht.
//
// Die LAUFNUMMER (`uploadLauf`) ist die Ordnung je GESPRÄCH: alle Uploads
// desselben Gesprächs laufen unter derselben Nummer, damit zwei gleichzeitige
// Dateien einander nicht entwerten. Erst ein Gesprächswechsel (`abbrechen`)
// erhöht sie; eine späte Antwort findet ihre Nummer dann nicht mehr gültig und
// trägt nichts ein. Ohne das landete der Anhang des ALTEN Gesprächs in der
// Liste des neuen, und `chat.senden` lehnte ihn mit „Anhang nicht gefunden.“ ab.
const anhaenge = ref([])
const anhangHinweis = ref('')
/**
 * Die eingestellte Höchstgröße je Anhang in BYTES (CHAT-12c) — aus der
 * Antwort von `chat.meine_gespraeche` (`anhang_max_bytes`), die die Seite
 * ohnehin lädt; kein zweiter Rundlauf. Startwert ist der Standard, damit die
 * Vorab-Prüfung auch vor der ersten Antwort eine Zahl nennt.
 */
const anhangGrenze = ref(anhangMaxBytes(null))
const dateiFeld = ref(null)
const anhangLauf = uploadLauf()
/**
 * Die Adress-Basis für Anhänge — DIESELBE wie für jeden API-Aufruf
 * (`apiUrl`, mit Betriebs-Präfix). Die Blase bekommt sie als Prop, damit
 * `<img src>`/`<a href>` nicht an einem zweiten Adressbau hängen.
 */
const anhangBasis = (methode) => apiUrl(methode)

/** Darf JETZT gesendet werden? (Text ODER Anhang, kein laufender Upload) */
const darfSendenJetzt = computed(() => darfSendenMitAnhang({
  gespraech: offeneKennung.value,
  text: text.value,
  liste: anhaenge.value,
  sendet: false,
}))

/**
 * Warum der Sende-Knopf gesperrt ist (`title` — ein echtes `disabled`
 * verschluckt den Tooltip; DkButton setzt `aria-disabled` zusätzlich).
 */
const sendenSperrgrund = computed(() => {
  if (darfSendenJetzt.value) return ''
  if (laedtNoch(anhaenge.value)) return 'Ein Anhang wird noch hochgeladen.'
  return ''
})

/** Die Büroklammer öffnet die Dateiauswahl des Systems. */
function dateiWaehlen() {
  const feld = dateiFeld.value
  if (!feld || typeof feld.click !== 'function') return
  anhangHinweis.value = ''
  // Ein erneutes Wählen derselben Datei muss wieder ein `change` auslösen.
  try { feld.value = '' } catch { /* manche Browser erlauben das nicht */ }
  feld.click()
}

/**
 * Auswahl aus dem Dateidialog: erst prüfen (Größe, Anzahl), dann je Datei
 * SOFORT hochladen. Die Vorab-Prüfung spart den Upload, den der Server sonst
 * mit 413/429 ablehnte — den TYP prüft er (Magie), nicht der Browser.
 *
 * Gezählt werden nur Einträge, die einen Platz BELEGEN (fertig oder laufend) —
 * gescheiterte Chips stehen bloß als Auskunft da (`fehlerZahl`) und dürfen eine
 * neue Auswahl nicht blockieren.
 */
function dateienGewaehlt(ereignis) {
  const dateien = [...((ereignis?.target?.files) || [])]
  if (!dateien.length) return
  const gespraech = offeneKennung.value
  if (!gespraech) {
    anhangHinweis.value = 'Bitte zuerst ein Gespräch öffnen.'
    return
  }
  // CHAT-12c: geprüft wird gegen die EINGESTELLTE Höchstgröße
  // (`anhang_max_bytes` aus `chat.meine_gespraeche`), nicht gegen eine Zahl in
  // der Oberfläche. Der Satz nennt dieselbe Zahl („max. 25 MB“).
  const pruefung = auswahlPruefen(dateien, anhaenge.value.length, fehlerZahl.value, anhangGrenze.value)
  if (!pruefung.ok) {
    anhangHinweis.value = pruefung.text
    return
  }
  anhangHinweis.value = ''
  for (const datei of pruefung.dateien) hochladen(datei, gespraech)
}

/** Wie viele Chips einen Platz belegen (alles außer „fehler“). */
const belegteZahl = computed(() => anhaenge.value.filter((c) => c.stand !== 'fehler').length)
/** Wie viele Chips nur noch als Auskunft stehen (Upload gescheitert). */
const fehlerZahl = computed(() => anhaenge.value.filter((c) => c.stand === 'fehler').length)

/**
 * EINE Datei hochladen — Multipart über `chat.anhang_hochladen`.
 *
 * Bewusst rohes `fetch`: `apiCall` erzwingt JSON, ein Datei-Upload ist
 * Multipart. Die Sitzungs- und CSRF-Prüfung kommt trotzdem von der einen
 * Stelle (`apiAntwortPruefen`, derselbe Weg wie `uploadDatei` in
 * `usePlanrahmen.js`) — die Anfrage wird als Funktion übergeben, damit eine
 * CSRF-Ablehnung mit frischem Token genau EINMAL wiederholt werden kann (ein
 * verbrauchter Body lässt sich nicht erneut senden).
 *
 * Die Antwort findet ihren Chip über die EIGENE Kennung (`chipeigen`) — nicht
 * über Name/Größe, die zwei Dateien teilen können. Die Laufnummer des
 * Gesprächs (`nummer`) entscheidet, ob sie überhaupt noch hierher gehört.
 *
 * Kein Fortschritt in Prozent: `fetch` meldet keinen, und eine geschätzte Zahl
 * wäre geraten. Der Chip sagt „wird hochgeladen …“.
 */
async function hochladen(datei, gespraech) {
  // Kurz prüfen, ob noch ein Platz frei ist (zwei Auswahlen kurz hintereinander):
  // die Karte erlaubt drei belegte Anhänge.
  if (belegteZahl.value >= ANHAENGE_MAX) {
    anhangHinweis.value = ANHANG_TEXTE.hoechstzahl
    return
  }
  const nummer = anhangLauf.neu()
  const chipeigen = `anhang-${anhangZaehler += 1}`
  const chip = chipBauen(datei, { lauf: nummer, gespraech, id: chipeigen })
  anhaenge.value = [...anhaenge.value, chip]
  const anfrage = () => {
    const form = new FormData()
    form.append('gespraech', gespraech)
    form.append('datei', datei, String(datei?.name || 'anhang'))
    return fetch(apiUrl('chat.anhang_hochladen'), {
      method: 'POST',
      headers: { 'X-Frappe-CSRF-Token': window.__DIakonosBOOT?.csrf_token || '' },
      body: form,
    })
  }
  /**
   * Gehört die Antwort noch hierher? Nur dann darf sie schreiben: dasselbe
   * Gespräch und eine gültige Laufnummer (`anhangAntwortGilt`) — und der Chip
   * muss noch in der Liste stehen, denn eine entfernte Datei hat kein Ziel mehr.
   */
  const nochHier = () => anhangAntwortGilt(chip, {
    nummer,
    gespraech: offeneKennung.value,
    gilt: anhangLauf.gilt,
  }) && anhaenge.value.some((c) => c.schluessel === chipeigen)
  try {
    const erste = await anfrage()
    const daten = await apiAntwortPruefen(erste, { anfrage })
    const res = daten?.dkAntwort || erste
    if (!res.ok || daten?.exc) {
      const fehler = new Error(daten?.message || daten?.exception || `HTTP ${res.status}`)
      fehler.status = res.status
      throw fehler
    }
    const lage = uploadAntwort(daten?.message)
    if (!lage.ok) throw new Error(lage.text)
    if (!nochHier()) return
    anhaenge.value = chipAendern(anhaenge.value, chipeigen, {
      stand: 'fertig', name: lage.name,
      dateiname: lage.dateiname || chip.dateiname,
      mime: lage.mime || chip.mime,
      groesse: lage.groesse || chip.groesse,
      fehler: '',
    })
  } catch (fehler) {
    // Ein entwerteter Lauf schreibt NICHTS — auch keinen Fehler (das Gespräch
    // ist ein anderes, die Meldung gehörte zu einem Ort, den es nicht mehr gibt).
    if (!nochHier()) return
    anhaenge.value = chipAendern(anhaenge.value, chipeigen, {
      stand: 'fehler',
      fehler: uploadFehlerText(fehler),
    })
  }
}

/** Fortlaufende Kennung der Chips (nur innerhalb dieser Seite). */
let anhangZaehler = 0

/**
 * Einen Chip aus der Liste nehmen. Bei einem FERTIGEN Anhang bleibt die Datei
 * im Server liegen — der Minuten-Job räumt sie weg (24 h), weil sie an keiner
 * Nachricht hängt.
 */
function anhangEntfernen(chip) {
  anhaenge.value = chipEntfernen(anhaenge.value, chip?.schluessel)
  anhangHinweis.value = ''
}

/**
 * Die Liste der offenen Anhänge leeren — nach dem Senden und beim
 * Gesprächswechsel. `verwerfen` entwertet zusätzlich alle laufenden Uploads:
 * ihre späten Antworten tragen dann nichts mehr ein (Karte Punkt 2).
 */
function anhaengeLeeren({ verwerfen = false } = {}) {
  if (verwerfen) anhangLauf.abbrechen()
  anhaenge.value = []
  anhangHinweis.value = ''
}

function zuruecksetzen() {
  // CHAT-11b-2: Der Sprung ÜBERLEBT das Öffnen SEINES Gesprächs (die Seite
  // lädt beim Wechsel neu, der `hashchange`-Watcher ruft hier auf) — sonst
  // fiele das Ziel genau dann weg, wenn es gebraucht wird. Ein anderes
  // Gespräch bricht ihn ab, ohne Hinweis.
  const sprungZielBleibt = Boolean(sprungNachricht.value)
    && String(offeneKennung.value || '') === String(sprungGespraech.value || '')
  nachrichten.value = []
  verlaufFehler.value = ''
  eingabeFehler.value = ''
  antwortAuf.value = null
  // `null` = kein Stand: der neu geladene Verlauf entscheidet (R1/3).
  aelterMoeglich.value = null
  eintrittHinweisRoh.value = ''
  // CHAT-7b-UI: Meldungen gehörten zum ALTEN Gespräch — „Runde verlassen“
  // scheiterte, die Vorschlagszeile antwortete nicht. Im nächsten Gespräch
  // dürfen sie nicht mehr stehen.
  verlassenFehler.value = ''
  vorschlagFehler.value = {}
  vorschlagLaeuft.value = ''
  // Die Teilnehmerliste stand im aufgeklappten Kopf des alten Gesprächs.
  teilnehmerOffen.value = false
  // CHAT-9b: der Merker der Erwähnungen gilt je GESPRÄCH — „@Anna“ im Chor
  // meint nicht die Anna der Runde.
  erwaehnungMerker.value = []
  erwaehnungSchliessen()
  // CHAT-9b-2: Die gemerkten Antworten gehören zu (Gespräch, q) — beim
  // Gesprächswechsel fallen die Suchläufe des alten Gesprächs weg.
  erwaehnungUnterdrueckt.value = -1
  erwaehnungAntworten.value = {}
  erwaehnungTextJeSchluessel.value = {}
  erwaehnungGefragt.value = null
  erwaehnungZuletztBeantwortet.value = null
  erwaehnungLaeuft.clear()
  // CHAT-7a: die Sperre gilt je GESPRÄCH, nicht für die Seite — ein anderes
  // 1:1 darf wieder schreibbar sein.
  sendenVonServerGesperrt.value = false
  // CHAT-11b: Sprung-Zustand und die Suche im Gespräch gehören zum GESPRÄCH
  // (Kennungen des alten Verlaufs wären hier falsch).
  if (!sprungZielBleibt) {
    // Review R1/1: Ein Wechsel in ein DRITTES Gespräch beendet den Sprung —
    // über die Laufnummer, damit eine noch wartende Schleife ihren falschen
    // „gibt es nicht mehr“-Satz nicht mehr schreiben kann.
    // CHAT-11b-3/2: Die Sperre hängt an der Laufnummer — der alte Lauf ist
    // damit entwertet und ein neuer Sprung darf sofort starten. Seine
    // Wartenden (`sprungFertig`) werden hier aufgelöst, damit niemand auf den
    // abgebrochenen Lauf wartet.
    if (sprungLaeuft) {
      sprungLaufNr += 1
      sprungLaeuft = false
      sprungAbschliessen()
    }
    sprungAbbrechen()
    sprungHinweis.value = ''
  }
  markierteNachricht.value = ''
  if (markierTimer) { clearTimeout(markierTimer); markierTimer = null }
  gespraechTrefferSchliessen()
  // CHAT-12b: offene Anhänge gehören zum GESPRÄCH — beim Wechsel fallen sie
  // weg, laufende Uploads werden entwertet (ihre späten Antworten tragen
  // nichts mehr ein, s. `anhaengeLeeren`). Ein „Foto ohne Worte“ im Chor darf
  // nicht in der Runde landen.
  anhaengeLeeren({ verwerfen: true })
  geoeffnet.value = ''
}

/** Gespräch öffnen: Verlauf holen, Lesestand setzen, Fokus in den Verlauf. */
async function oeffnen() {
  // Review R1/1: Der Sprung braucht einen Punkt, an dem der Verlauf GENAU
  // DIESES Gesprächs wirklich steht — die Adresse allein sagt das nicht
  // (`hashchange` kommt als eigener Task). Darum liegt der laufende Aufbau
  // hier als Zusage (`offenLaeuft`), auf die `sprungBereit` wartet.
  const lauf = oeffnenJetzt()
  offenLaeuft = lauf
  try {
    return await lauf
  } finally {
    if (offenLaeuft === lauf) offenLaeuft = null
  }
}

async function oeffnenJetzt() {
  const offen = offeneKennung.value
  if (!offen) return
  // Schon geladen (z. B. das erste Zeichen einer Suche lässt das Gespräch
  // offen): KEIN zweites Laden, kein zweiter Lesestand (Review R1, MUSS 1).
  if (offen === geoeffnet.value) return
  zuruecksetzen()
  // Ein Gespräch, das noch nie geöffnet wurde, hat serverseitig KEINE Kennung
  // (`geoeffnet: false`). Hier wird es angelegt (`gespraech_anlegen`, lazy im
  // Server) und die Adresse auf die neue Kennung gestellt — EIN Weg, kein
  // Sonderfall im Verlauf.
  if (!(await sicherstellen())) return
  const daten = await verlaufLaden()
  if (daten) await lesestandSetzen()
  // CHAT-7b-UI: beim Öffnen einer RUNDE die Teilnehmerliste einklappen — die
  // Namen kommen mit der Antwort (`mitglieder`), es wird nichts nachgeschlagen.
  if (istOffeneRunde.value) teilnehmerOffen.value = false
  // Karte Punkt 5: Fokus nach Gesprächswechsel in den Verlauf — die neue
  // Region wird vorgelesen, der Fokus bleibt nicht im alten Gespräch.
  await nextTick()
  if (verlaufEl.value && typeof verlaufEl.value.focus === 'function') verlaufEl.value.focus()
  await nachUntenScrollen()
}

/**
 * Der Eintrag einer Adresse, die noch keine Gesprächszeile hat (sonst `null`).
 *
 * Review R1: adressiert wird über den ORT (Gruppe + Untergruppe), nicht über
 * den Titel — zwei Untergruppen können denselben Anzeigenamen tragen, und der
 * Titel ist frei.
 *
 * CHAT-3a-3/C1 (Review Runde 2): Ein Hauptgruppen-Name („Jugend“) durfte NICHT
 * die Untergruppe („Jugend – Leiter“) treffen. Vorher stand hier
 * `e.gruppe === a || e.untergruppe === a` — bei `a = 'Jugend'` passte auch der
 * Eintrag der Untergruppe, denn dessen `gruppe` ist ebenfalls „Jugend“; der
 * Server sortiert nie geöffnete Einträge nach Titel ABSTEIGEND, „Jugend –
 * Leiter“ stand also VOR „Jugend“, und der falsche Chat wurde geöffnet (und
 * angelegt). Die Adresse nennt jetzt GENAU eine Einheit:
 *
 *   * Hauptgruppe  → `!e.untergruppe && e.gruppe === a` (nur der Haupt-Chat),
 *   * Untergruppe  → `e.untergruppe === a` (die Untergruppe ist eindeutig),
 *   * `gruppe/untergruppe` → beide Felder zusammen.
 */
function ungeoeffneteZeile(adresse) {
  const a = String(adresse || '')
  if (!a) return null
  return gespraeche.value.find((e) => {
    if (e.name || e.geoeffnet !== false) return false
    const gruppe = String(e.gruppe || '')
    const unter = String(e.untergruppe || '')
    if (unter) return unter === a || `${gruppe}/${unter}` === a
    return gruppe === a
  }) || null
}

/**
 * Stellt sicher, dass das Gespräch der Adresse EXISTIERT (legt es bei Bedarf an)
 * und die Adresse auf seine Kennung zeigt. `true` = es kann geladen werden.
 */
async function sicherstellen() {
  const ziel = kennung.value
  if (!ziel) return true // Suche: das Gespräch rechts ist schon da (`&offen=`)
  if (gespraeche.value.some((e) => String(e?.name || '') === ziel)) return true
  const neu = ungeoeffneteZeile(ziel)
  if (!neu) return true // unbekannte Kennung: der Verlauf meldet „gibt es nicht“
  try {
    const angelegt = await apiCall('chat.gespraech_anlegen', {
      gruppe: neu.gruppe,
      untergruppe: neu.untergruppe || undefined,
    })
    const kennungNeu = String(angelegt?.name || '')
    if (!kennungNeu) return false
    // Die Liste kennt den Eintrag jetzt als geöffnet — ohne zweiten Abruf.
    gespraeche.value = gespraeche.value.map((e) => (e === neu
      ? { ...e, name: kennungNeu, geoeffnet: true, art: angelegt?.art || e.art }
      : e))
    // Die Adresse auf die echte Kennung stellen (ersetzt den Platzhalter-Titel).
    // Verglichen wird der PFAD ohne Abfrageteil — ein `?…` darf den Wechsel nicht
    // verhindern und auch nicht mitgeschleppt werden.
    const zielHash = gespraechHash(kennungNeu)
    const aktuell = typeof window === 'undefined' ? '' : String(window.location.hash || '').split('?')[0]
    if (typeof window !== 'undefined' && aktuell !== zielHash) {
      window.location.replace(zielHash)
      return false // der hashchange-Handler lädt den Verlauf
    }
    if (typeof window !== 'undefined' && String(window.location.hash || '') !== zielHash) {
      // Derselbe Pfad, aber mit Abfrageteil (`#/suche?…&offen=<ort>`): die
      // Adresse auf die Kennung stellen, BEVOR die Kennung übernommen wird —
      // sonst liest ein `hashGeaendert` die alten Werte zurück.
      window.history.replaceState({}, '', zielHash)
      hashGeaendert()
      return false // der hashchange-Handler lädt den Verlauf
    }
    kennung.value = kennungNeu
    return true
  } catch (fehler) {
    listeFehlerRoh.value = fehler
    return false
  }
}

/**
 * Neueste Seite laden (erstes Öffnen und Polling).
 *
 * CHAT-3a-3/B (Review Runde 2): Der Poll schickt KEIN `seit` mehr. `seit`
 * liefert serverseitig nur Nachrichten mit SPÄTEREM Zeitstempel
 * (`api/chat.py`, `verlauf` → `ChatNachricht.erstellt_am > anker`) — eine
 * Bearbeitung, eine Löschung (samt `geloescht_grund`), eine neue Reaktion oder
 * ein geänderter Lesestand einer schon sichtbaren Nachricht kam damit NIE an.
 * Ohne `seit` antwortet der Server mit `richtung: 'neueste'` — der vollen,
 * jüngsten Seite; `seiteEinordnen` ersetzt bekannte Zeilen in place, hängt
 * neue hinten an und zählt `aktualisiert`. Ein verschobener Verlauf ist damit
 * der Normalfall, kein Sonderfall (`istAeltereSeite` fragt die `richtung`).
 *
 * @returns {boolean} ob geladen wurde (für `lesestandSetzen`)
 */
async function verlaufLaden({ still = false } = {}) {
  const offen = offeneKennung.value
  if (!offen) return false
  if (!still) verlaufLaedt.value = true
  let erfolg = false
  try {
    const antwort = await apiGet('chat.verlauf', { gespraech: offen })
    if (!aktivSeite || offen !== offeneKennung.value) return false // inzwischen anderes Gespräch
    // CHAT-7b-UI (Karte Punkt 5): der Server sagt, ob hier jemand erst später
    // dazugekommen ist — ohne das Feld bleibt der Hinweis leer.
    eintrittHinweisRoh.value = eintrittsHinweis(antwort)
    const vorher = nachrichten.value
    const lage = seiteEinordnen(antwort, { alt: vorher, ich: ich.value })
    nachrichten.value = lage.nachrichten
    // „nachladen nach oben“: NUR ein voller, älterer Abruf ändert das; die
    // neueste Seite und der Poll sagen nichts darüber (`aelterStand`).
    // Review R1/3: Ohne bisherigen Stand entscheidet der geladene Verlauf
    // (volle Seite = oben geht es weiter), sonst behält die Seite ihren Stand.
    aelterMoeglich.value = aelterStand(aelterMoeglich.value, lage.aelterMoeglich, lage.nachrichten.length)
    verlaufFehler.value = ''
    verlaufHinweis.value = ''
    erfolg = true
    if (still) {
      // MUSS 2: neue fremde Nachrichten in einem SICHTBAREN Tab sind gelesen —
      // Lesestand melden, sonst bliebe der Zähler stehen.
      if (lesestandFaellig({
        neuHinzugefuegt: lage.neuHinzugefuegt,
        neueFremde: fremdeNeue(vorher, lage.nachrichten),
        ungelesen: Number(offenesGespraech.value?.ungelesen) || 0,
        sichtbar: tabSichtbar(),
      })) {
        await lesestandSetzen()
      }
      if (lage.neuHinzugefuegt > 0) await nachUntenScrollen({ erzwingen: false })
    }
  } catch (fehler) {
    if (!aktivSeite || offen !== offeneKennung.value) return false
    if (still) {
      // Ein misslungener Poll behält den letzten guten Verlauf und zeigt nur
      // einen kleinen Hinweis (Review R1).
      verlaufHinweis.value = 'Der Verlauf konnte gerade nicht aktualisiert werden.'
    } else {
      const zustand = fehlerZustand(fehler)
      verlaufFehler.value = zustand ? `${zustand.titel}. ${zustand.text}` : fehlertext(fehler)
    }
  } finally {
    if (!still) verlaufLaedt.value = false
  }
  if (!erfolg) {
    // Merken nur, wenn der Verlauf wirklich hier steht — ein misslungener
    // Abruf darf ein späteres Öffnen nicht überspringen.
    return false
  }
  geoeffnet.value = offen
  return true
}

/**
 * Nachladen nach OBEN: die Seite VOR der ältesten bekannten Nachricht.
 *
 * `ohnePosition` (CHAT-11b): beim SPRUNG bleibt die Leseposition nicht
 * stehen — es wird ohnehin gleich zur gefundenen Nachricht gerollt.
 *
 * CHAT-11b-2/2: Läuft schon ein Nachladen, wird DARAUF GEWARTET (das laufende
 * Promise liegt in `aelterLauf`) — sonst hätte der Sprung den Tick als
 * Ladeversuch gezählt und nach ~10 Ticks fälschlich „gibt es nicht mehr“
 * gezeigt. Der Rückgabewert sagt, ob SEIN Aufruf eine Seite geholt hat; ein
 * Wartender bekommt das Ergebnis des laufenden.
 *
 * Review R1/2: der Lauf gehört EINEM Gespräch (`{ gespraech, lauf }`). Ein
 * Nachladen, das noch im ALTEN Gespräch hängt, wird nie einem Sprung im neuen
 * zurückgegeben — der bekäme sonst `false` für eine Seite, die er nie geholt
 * hat. Ein Lauf eines anderen Gesprächs zählt hier als „läuft nicht“: das neue
 * Gespräch holt seine eigene Seite, der alte Lauf schreibt ohnehin nichts mehr
 * (er prüft `offen !== offeneKennung`).
 *
 * @returns {Promise<boolean>} ob eine ältere Seite geladen wurde
 */
async function aeltereLaden({ ohnePosition = false } = {}) {
  const offen = offeneKennung.value
  if (!offen || !nachrichten.value.length) return false
  if (aelterLauf && aelterLauf.gespraech === offen) return aelterLauf.lauf
  const lauf = aeltereLadenJetzt({ ohnePosition })
  const eintrag = { gespraech: offen, lauf }
  aelterLauf = eintrag
  try {
    return await lauf
  } finally {
    if (aelterLauf === eintrag) aelterLauf = null
  }
}

/**
 * Das laufende Nachladen (oder `null`) — s. `aeltereLaden`. Es hängt an SEINEM
 * Gespräch: ein Wechsel macht den alten Lauf für die neue Seite bedeutungslos.
 */
let aelterLauf = null

/** Läuft gerade ein Nachladen für DIESES Gespräch? (s. `aeltereLaden`) */
function aelterLaeuftIn(gespraech) {
  const g = String(gespraech || '')
  return Boolean(g && aelterLauf && aelterLauf.gespraech === g)
}

/**
 * Das laufende Nachladen des Gesprächs — oder `null`. Scheitert es, ist das
 * hier kein Fehler: der nächste Schritt entscheidet neu (Review R1/2).
 */
function aelterWarten(gespraech) {
  if (!aelterLaeuftIn(gespraech)) return null
  return Promise.resolve(aelterLauf.lauf).catch(() => false)
}

async function aeltereLadenJetzt({ ohnePosition = false } = {}) {
  const offen = offeneKennung.value
  aelterLaedt.value = true
  const anker = nachrichten.value[0].ident
  scrollVorher = ohnePosition ? 0 : (verlaufEl.value ? verlaufEl.value.scrollHeight : 0)
  let geladen = false
  try {
    const antwort = await apiGet('chat.verlauf', { gespraech: offen, vor: anker })
    if (offen !== offeneKennung.value) return false
    const lage = seiteEinordnen(antwort, { alt: nachrichten.value, ich: ich.value })
    nachrichten.value = lage.nachrichten
    aelterMoeglich.value = aelterStand(aelterMoeglich.value, lage.aelterMoeglich)
    geladen = true
    await nextTick()
    // Die gelesene Stelle bleibt stehen: die neuen Zeilen stehen OBEN, deshalb
    // wird um die hinzugekommene Höhe nachgeschoben (sonst springt der Verlauf).
    if (!ohnePosition && verlaufEl.value && scrollVorher && offen === offeneKennung.value) {
      verlaufEl.value.scrollTop = verlaufEl.value.scrollHeight - scrollVorher
    }
  } catch (fehler) {
    if (offen === offeneKennung.value) {
      const zustand = fehlerZustand(fehler)
      verlaufFehler.value = zustand ? `${zustand.titel}. ${zustand.text}` : fehlertext(fehler)
    }
  } finally {
    // Review R1/2: Nur der Lauf des OFFENEN Gesprächs schaltet die Anzeige ab —
    // ein Lauf, der im alten Gespräch hängen blieb, ließe das neue sonst
    // fälschlich „lädt nicht“ anzeigen.
    if (offen === offeneKennung.value) aelterLaedt.value = false
  }
  return geladen
}

/** Am Anfang des Verlaufs angekommen → ältere Seite holen (Karte Punkt 1). */
function beimScrollen() {
  const el = verlaufEl.value
  if (!el || !aelterMoeglich.value || aelterLaedt.value) return
  if (el.scrollTop <= 24) aeltereLaden()
}

/** Ist der Verlauf ganz unten? (Toleranz für Restluft und Rundung.) */
function istUnten() {
  const el = verlaufEl.value
  if (!el) return true
  return el.scrollHeight - el.scrollTop - el.clientHeight <= 24
}

/**
 * CHAT-3a-4 (MUSS 1): Ans Ende springen — beim Öffnen und bei einer neuen
 * eigenen Nachricht, aber NICHT, wenn der Nutzer oben liest.
 *
 * `erzwingen` = Pflichtlauf (Öffnen, eigene Nachricht); ohne ihn gilt: nur
 * springen, wenn der Verlauf ohnehin unten stand. Nachrücken (`nachfuehren`)
 * holt die Eingabe am Handy ins Bild, wenn die SEITE zu tief steht (offene
 * Tastatur) — der Verlauf selbst scrollt in seinem eigenen Kasten.
 */
async function nachUntenScrollen({ erzwingen = true } = {}) {
  if (!erzwingen && !istUnten()) {
    // Der Nutzer liest weiter oben: KEIN Sprung (Karte MUSS 1) — und auch
    // KEIN Nachführen (CHAT-3a-5, D): `form.scrollIntoView` zog die SEITE
    // nach unten, obwohl der Verlauf absichtlich stehen blieb.
    return
  }
  await nextTick()
  if (verlaufEl.value) verlaufEl.value.scrollTop = verlaufEl.value.scrollHeight
  nachfuehren()
}

/**
 * Die Eingabe ins Bild holen, wenn die SEITE zu tief steht (Handy, Tastatur).
 *
 * CHAT-3a-5 (D): Gerufen wird das nur noch, wenn wirklich ans Ende gesprungen
 * wurde. Wer oben liest, bekommt keinen Sprung — weder im Verlauf noch in der
 * Seite.
 */
async function nachfuehren() {
  if (typeof document === 'undefined' || istHandyLage.value !== true) return
  await nextTick()
  const form = typeof document.getElementById === 'function'
    ? document.getElementById('chat-eingabe-form')
    : null
  if (form && typeof form.scrollIntoView === 'function') {
    try { form.scrollIntoView({ block: 'end' }) } catch { /* egal */ }
  }
}

/** Verlauf mit Tages-Marken für die Anzeige (Heute/Gestern/Wochentag/Datum). */
const nachrichtenMitTag = computed(() => mitTagesmarken(nachrichten.value))

/**
 * CHAT-3a-4 (MUSS 2): Avatar-Spalte je Zeile — die Regel steht in
 * `composables/nachrichtenLogik.mjs` (`folgeStarten`, ohne DOM prüfbar).
 * Der Avatar gehört an den Folgenanfang (gleicher Autor, gleicher Tag).
 */
const folgenStart = computed(() => folgeStarten(nachrichtenMitTag.value))
function folgeStart(i) {
  return folgenStart.value[i] !== false
}

// ── Lesestand, Stumm ───────────────────────────────────────────────────────

/**
 * Lesestand setzen — beim Öffnen und nach neuen Nachrichten. Die Antwort trägt
 * den neuen Zähler des Gesprächs; er wird in die Liste übernommen (kein
 * zweiter Abruf), damit „ungelesen“ sofort stimmt.
 */
async function lesestandSetzen() {
  const offen = offeneKennung.value
  if (!offen) return
  try {
    const antwort = await apiCall('chat.lesestand_setzen', { gespraech: offen })
    const zahl = Number(antwort?.ungelesen)
    if (Number.isInteger(zahl)) {
      gespraeche.value = gespraeche.value.map((e) => (String(e?.name || '') === String(offen)
        ? { ...e, ungelesen: zahl }
        : e))
      mitteilungSenden()
    }
  } catch {
    // Der Lesestand ist Beiwerk — ein Fehler darf das Lesen nicht stören.
  }
}

async function stummUmschalten() {
  const offen = offeneKennung.value
  const eintrag = offenesGespraech.value
  if (!offen || !eintrag) return
  const an = eintrag.stumm !== true
  try {
    await apiCall('chat.stumm_setzen', { gespraech: offen, an })
    gespraeche.value = gespraeche.value.map((e) => (String(e?.name || '') === String(offen)
      ? { ...e, stumm: an }
      : e))
  } catch (fehler) {
    verlaufFehler.value = fehlertext(fehler)
  }
}

// ── Eingabe, Antworten ─────────────────────────────────────────────────────

/**
 * CHAT-9b: Die Beteiligten, die „@“ anbietet — und die Kennungen hinter den
 * eingesetzten Namen.
 *
 * QUELLE (Operator-Entscheidung R1, EINE Abfrage für ALLE Gesprächsarten):
 * `chat.gespraech_mitglieder(gespraech, q, limit)` (GET, Backend-Karte
 * CHAT-9c-2) → `{art, mitglieder: [{mitglied, anzeigename}], mehr}`. Der
 * Server liefert den VOLLEN Namen (dieselbe Quelle wie `erwaehnt[].anzeigename`
 * in jeder Nachrichtenzeile) und lässt die lesende Person weg — genau deshalb
 * gibt es die früheren Quellen `titel` (1:1) und `mitglieder` aus
 * `meine_gespraeche` (Runde) hier NICHT mehr: zwei Quellen hießen zwei
 * Schreibweisen, und der eingesetzte Name müsste den Namen treffen, den der
 * Server später speichert.
 *
 * CHAT-9b-2: NICHT mehr die Vollliste je Gespräch, sondern die Frage je
 * Namensanfang — entprellt (200 ms, der BESTEHENDE `entpreller`), Antworten
 * je `(gespraech, q)` gemerkt, veraltete Antworten verworfen (nur der
 * Schlüssel des AKTUELLEN `q` zählt). Bis die Antwort da ist, filtert
 * `vorschlaege` die zuletzt bekannte Liste lokal weiter — das flackert nicht.
 * Scheitert die Abfrage (403/404/Netz), bleibt die Auswahl still weg; der
 * Fehler wird NICHT gemerkt: beim nächsten Tippen darf sie es erneut wagen.
 */
const ERWAEHNUNG_LISTE = 'dk-erwaehnung-liste'
const erwaehnungOffen = ref(false)
const erwaehnungStelle = ref(null)
const erwaehnungAktiv = ref(0)
const erwaehnungMerker = ref([])
/** R1/1: Stelle (Textposition des „@“), an der Escape die Liste geschlossen hat. */
const erwaehnungUnterdrueckt = ref(-1)
/**
 * Gemerkte Antworten: `{ [schluessel]: {mitglieder, mehr} }` mit
 * `schluessel = erwaehnungSchluessel(gespraech, q)`. Die Liste zur LEEREN
 * Frage („@“ allein, erste 20) liegt ebenfalls hier.
 */
const erwaehnungAntworten = ref({})
/** Der Schlüssel, auf den die Auswahl gerade wartet/zeigt (`null` = keine Frage). */
const erwaehnungGefragt = ref(null)
/**
 * R1/2: Der Schlüssel der zuletzt BEANTWORTETEN Frage desselben Gesprächs.
 * Solange die Antwort zum aktuellen `q` läuft, filtert `erwaehnungTreffer`
 * DIESE Liste lokal — sonst ginge die Auswahl bei jedem Tastendruck zu.
 */
const erwaehnungZuletztBeantwortet = ref(null)
/**
 * Der GETIPPTE Text je Schlüssel (`{[schluessel]: 'An'}`) — gefragt wird der
 * Text so, wie er hinter dem „@“ steht; der Schlüssel ist nur falten-gleich.
 */
const erwaehnungTextJeSchluessel = ref({})
/** Läuft gerade eine Abfrage? (nur Anzeige — kein zweiter Aufruf derselben Frage) */
const erwaehnungLaeuft = new Set()

/** Die Vorschläge (ohne den „mehr“-Hinweis) — aus der gemerkten Antwort. */
function antwortFuer(schluessel) {
  const stand = erwaehnungAntworten.value[schluessel]
  return Array.isArray(stand?.mitglieder) ? stand.mitglieder : []
}

/**
 * Der Schlüssel, dessen Antwort die Auswahl zeigt (R1/2): der aktuelle, sonst
 * der zuletzt beantwortete desselben Gesprächs — siehe `antwortSchluessel`.
 */
const erwaehnungZeige = computed(() => antwortSchluessel(
  erwaehnungGefragt.value,
  erwaehnungZuletztBeantwortet.value,
  erwaehnungAntworten.value,
))

/**
 * Sagt der Server zu dieser Frage „es gibt mehr“?
 *
 * R1/3: Auch bei 0 Treffern — der Hinweis („weiter tippen“) steht dann allein
 * unter dem Feld, damit niemand denkt, der Name sei unauffindbar. Er hängt an
 * der GEZEIGTEN Antwort (solange die neue läuft, an der letzten bekannten).
 */
const erwaehnungMehr = computed(() => {
  const schluessel = erwaehnungZeige.value
  if (!erwaehnungOffen.value || !schluessel) return false
  return erwaehnungAntworten.value[schluessel]?.mehr === true
})

/** Die sichtbaren Vorschläge — Grundlage von `auswahlSichtbar` und `auswahlAnsage`. */
const erwaehnungTreffer = computed(() => {
  if (!erwaehnungOffen.value) return []
  const begriff = erwaehnungStelle.value?.begriff || ''
  return vorschlaege(antwortFuer(erwaehnungZeige.value), begriff, { ich: ich.value })
})

/**
 * R1/4: Ist die Auswahl WIRKLICH sichtbar? Offen UND mindestens ein Treffer.
 * Nur daran hängen `aria-expanded`, `aria-controls` und `aria-activedescendant`
 * — bei „@xyz“ ohne Treffer steht keine Liste im DOM, dann darf der
 * Vorleser auch keine sehen. (Der „mehr“-Hinweis zählt NICHT: er ist keine
 * Wahl und steht außerhalb der Listbox, R1/3.)
 */
const auswahlSichtbar = computed(() => erwaehnungOffen.value
  && erwaehnungTreffer.value.length > 0)

/** R1/5: Ansage für den Vorleser — „N Namen zur Auswahl“ (leer: nichts). */
const auswahlAnsage = computed(() => {
  const n = auswahlSichtbar.value ? erwaehnungTreffer.value.length : 0
  if (!n) return ''
  return n === 1 ? '1 Name zur Auswahl' : `${n} Namen zur Auswahl`
})

/**
 * Der Entpreller (derselbe wie in der Personensuche, `nachrichtenSuche.mjs`):
 * zwei schnelle Eingaben ergeben EINE Abfrage.
 *
 * R1/4: `darfFragen` hebt die Mindestlänge der Personensuche auf — hier zählt
 * JEDER Anfang: „@“ allein (erste 20) und ein Zeichen („@b“ → „Bert
 * Brandner“), so wie der Server es macht (CHAT-9c-2). Die Personensuche fragt
 * erst ab zwei Zeichen; das ist ihre Regel, nicht die der Erwähnung.
 */
const erwaehnungEntprellt = entpreller({
  warte: ERWAEHNUNG_ENTPRELLUNG_MS,
  darfFragen: () => true,
  beiFaelligkeit: (schluessel) => erwaehnungFragen(schluessel),
})

/**
 * Fragen — aber nur, wenn die Antwort nicht schon gemerkt ist. Läuft dieselbe
 * Frage bereits, wird nicht doppelt gefragt.
 */
async function erwaehnungFragen(schluessel) {
  const kennung = String(schluessel || '')
  if (!kennung || !aktivSeite) return
  // Gehört die Frage noch zur offenen Auswahl? (Gesprächswechsel, Escape,
  // eingesetzter Name: dann ist `erwaehnungGefragt` ein anderer Schlüssel.)
  if (schluessel !== erwaehnungGefragt.value) return
  if (erwaehnungAntworten.value[kennung] || erwaehnungLaeuft.has(kennung)) return
  const { gespraech, q } = erwaehnungSchluesselTeile(kennung)
  if (!gespraech) return
  erwaehnungLaeuft.add(kennung)
  try {
    // Gefragt wird der Text hinter dem „@“ — der Schlüssel ist nur die
    // Vergleichsform (falt-gleich) für „dieselbe Frage“.
    const antwort = await apiGet('chat.gespraech_mitglieder', {
      gespraech, q: erwaehnungFrage(erwaehnungTextJeSchluessel.value[kennung] ?? q), limit: ERWAEHNUNG_ANZAHL,
    })
    // Veraltete Antwort: die Auswahl steht längst auf einem anderen `q` — sie
    // wird verworfen (nicht einmal gemerkt: sie beantwortet keine offene Frage).
    if (!aktivSeite || schluessel !== erwaehnungGefragt.value) return
    erwaehnungAntworten.value = {
      ...erwaehnungAntworten.value,
      [kennung]: erwaehnungAntwort(antwort, { ich: ich.value }),
    }
    // R1/2: ab jetzt ist DIESE Antwort der Stand, an dem sich die nächste
    // Eingabe festhält, bis ihre eigene Antwort da ist.
    erwaehnungZuletztBeantwortet.value = kennung
  } catch {
    // Fehler (403/404/Netz): Auswahl still zu — kein Lärm, kein geratener Name.
    if (!aktivSeite || schluessel !== erwaehnungGefragt.value) return
    erwaehnungSchliessen()
  } finally {
    erwaehnungLaeuft.delete(kennung)
  }
}

/** Cursorstelle im Feld (Ende, wenn der Browser sie nicht hergibt). */
function cursorStelle() {
  const el = eingabeEl.value
  const pos = Number(el?.selectionStart)
  return Number.isInteger(pos) && pos >= 0 ? pos : String(text.value || '').length
}

/**
 * Nach jedem Tippen/Klicken: steht hinter einem „@“ ein offener Name?
 *
 * R1/1: Hat ESCAPE die Liste geschlossen, bleibt sie zu, bis NEU getippt wird
 * (`neueEingabe: true` vom `@input`): danach gilt die Unterdrückung nicht mehr.
 * Ohne beides hätte das `keyup` nach dem Escape (der Text steht ja unverändert
 * da) die Liste sofort wieder geöffnet.
 * CHAT-9b-2: Jede Änderung des Namensanfangs stellt die Frage `(gespraech, q)`
 * — entprellt. Die Auswahl steht sofort offen und zeigt, was schon gemerkt ist
 * (bei der ersten Frage: nichts, sie öffnet sich mit der Antwort); eine
 * Antwort auf ein anderes `q` zählt nicht.
 */
function erwaehnungPruefen({ neueEingabe = false } = {}) {
  const gespraech = offeneKennung.value
  if (!gespraech) return
  if (neueEingabe) erwaehnungUnterdrueckt.value = -1
  const stelle = offeneErwaehnung(text.value, cursorStelle())
  if (!stelle) {
    erwaehnungSchliessen()
    return
  }
  // Dieselbe Stelle, die Escape geschlossen hat: nicht wieder aufmachen.
  if (stelle.start === erwaehnungUnterdrueckt.value) {
    erwaehnungSchliessen()
    return
  }
  const schluessel = erwaehnungSchluessel(gespraech, stelle.begriff)
  const wechsel = schluessel !== erwaehnungGefragt.value
  erwaehnungStelle.value = stelle
  erwaehnungGefragt.value = schluessel
  // Der Text hinter dem „@“ (so wird gefragt; der Schlüssel vergleicht nur).
  erwaehnungTextJeSchluessel.value = {
    ...erwaehnungTextJeSchluessel.value,
    [schluessel]: erwaehnungFrage(stelle.begriff),
  }
  // Neue Frage: wieder oben anfangen (wie eine frische Liste).
  if (wechsel || !erwaehnungOffen.value) erwaehnungAktiv.value = 0
  erwaehnungOffen.value = true
  erwaehnungEntprellt.tippen(schluessel)
  const anzahl = auswahlAnzahl(erwaehnungTreffer.value)
  if (erwaehnungAktiv.value >= anzahl) erwaehnungAktiv.value = 0
}

/** `@input`: der Text hat sich geändert — eine alte Unterdrückung gilt nicht mehr. */
function erwaehnungGetippt() {
  erwaehnungPruefen({ neueEingabe: true })
}

/** Einen Vorschlag einsetzen: „@Anzeigename “ + Kennung merken. */
function erwaehnungWaehlen(eintrag) {
  const stelle = erwaehnungStelle.value
  if (!stelle) return
  const lage = einsetzen(text.value, stelle, eintrag, erwaehnungMerker.value)
  text.value = lage.text
  erwaehnungMerker.value = lage.merker
  erwaehnungOffen.value = false
  erwaehnungStelle.value = null
  erwaehnungAktiv.value = 0
  erwaehnungUnterdrueckt.value = -1
  // Cursor hinter das eingesetzte Leerzeichen — dort wird weitergetippt.
  nextTick(() => {
    const el = eingabeEl.value
    if (!el || typeof el.setSelectionRange !== 'function') return
    try {
      el.focus()
      el.setSelectionRange(lage.pos, lage.pos)
    } catch { /* egal */ }
  })
}

/**
 * Escape/Verlassen der Auswahl ohne Auswahl.
 *
 * R1/1: `unterdruecken` merkt die Stelle des „@“ — die Seite setzt es beim
 * Escape (dort steht der Cursor noch), beim Gesprächswechsel nicht.
 */
function erwaehnungSchliessen({ unterdruecken = false } = {}) {
  if (unterdruecken && erwaehnungStelle.value) {
    erwaehnungUnterdrueckt.value = erwaehnungStelle.value.start
  }
  // Offene Frage fallen lassen: eine späte Antwort gehört zu keiner Auswahl mehr.
  erwaehnungEntprellt.abbrechen()
  erwaehnungGefragt.value = null
  erwaehnungOffen.value = false
  erwaehnungStelle.value = null
  erwaehnungAktiv.value = 0
}

function beimTasten(ereignis) {
  // R1/3: Eine laufende Eingabemethode (IME) gehört dem Feld: Enter bestätigt
  // dort die Zeichenauswahl, Escape bricht sie ab. Hier wird nichts getan.
  if (istEingabemethode(ereignis)) return
  // CHAT-9b: Offene Auswahl frisst die Tasten, die ihr gehören (↑/↓/Enter/Tab/
  // Escape) — sonst sendete Enter die Nachricht, statt den Namen einzusetzen.
  const absichtAuswahl = auswahlTaste({
    key: ereignis.key,
    schift: ereignis.shiftKey,
    offen: auswahlSichtbar.value,
    anzahl: erwaehnungTreffer.value.length,
    aktiv: erwaehnungAktiv.value,
  })
  if (absichtAuswahl === 'weiter' || absichtAuswahl === 'zurueck') {
    ereignis.preventDefault()
    erwaehnungAktiv.value = naechsteStelle(
      erwaehnungAktiv.value,
      absichtAuswahl === 'weiter' ? 1 : -1,
      erwaehnungTreffer.value.length,
    )
    return
  }
  if (absichtAuswahl === 'waehlen') {
    ereignis.preventDefault()
    const eintrag = erwaehnungTreffer.value[erwaehnungAktiv.value]
    if (eintrag) erwaehnungWaehlen(eintrag)
    return
  }
  if (absichtAuswahl === 'schliessen') {
    ereignis.preventDefault()
    erwaehnungSchliessen({ unterdruecken: true })
    return
  }
  const absicht = tasteImFeld({
    key: ereignis.key,
    shiftKey: ereignis.shiftKey,
    isComposing: ereignis.isComposing,
  })
  if (absicht !== 'senden') return
  ereignis.preventDefault()
  senden()
}

/**
 * R1/1: Das `keyup` nach einer Taste, die NUR die Auswahl bediente, darf die
 * Liste nicht wieder öffnen. Escape und ↑/↓/Enter/Tab ändern den Text nicht —
 * `offeneErwaehnung` fände also wieder ein „@“ und die Liste spränge auf.
 */
function erwaehnungPruefenNachTaste(ereignis) {
  if (istEingabemethode(ereignis)) return
  if (nurAuswahlTaste(ereignis?.key)) return
  erwaehnungPruefen()
}

async function senden() {
  const offen = offeneKennung.value
  if (!offen || sendet.value) return
  // CHAT-12b: solange ein Upload läuft, ginge die Nachricht OHNE den Anhang
  // hinaus (die Kennung kennt der Server noch nicht) — also nicht senden.
  if (laedtNoch(anhaenge.value)) {
    eingabeFehler.value = ''
    anhangHinweis.value = 'Ein Anhang wird noch hochgeladen — einen Moment.'
    return
  }
  const kennungenAnhang = anhangKennungen(anhaenge.value)
  const pruefung = pruefeText(text.value, { mitAnhang: kennungenAnhang.length > 0 })
  if (!pruefung.ok) {
    eingabeFehler.value = pruefung.fehler
    return
  }
  sendet.value = true
  eingabeFehler.value = ''
  anhangHinweis.value = ''
  try {
    // CHAT-9b: geschickt wird nur, wessen „@Anzeigename“ JETZT noch im Text
    // steht — wer den Namen gelöscht oder verändert hat, ist nicht mehr
    // gemeint. Ohne Erwähnung geht KEIN Feld hinaus (der Server liest dort
    // „keine“).
    const kennungen = auswahlBereinigen(pruefung.text, erwaehnungMerker.value, { ich: ich.value })
    // CHAT-12b: die Kennungen der FERTIGEN Anhänge gehen mit; ohne Anhang
    // steht das Feld gar nicht in der Anfrage.
    const args = sendeRumpf({
      gespraech: offen,
      text: pruefung.text,
      anhaenge: kennungenAnhang,
      antwortAuf: antwortAuf.value?.ident || '',
      erwaehnt: kennungen,
    })
    const neu = await apiCall('chat.senden', args)
    const zeile = verlaufsZeile(neu, { ich: ich.value })
    if (zeile) nachrichten.value = [...nachrichten.value.filter((n) => n.ident !== zeile.ident), zeile]
    text.value = ''
    // Gesendet heißt: die offene Liste ist leer (die Anhänge hängen jetzt an
    // der Nachricht — ein zweites Senden dürfte sie nicht wieder mitnehmen).
    anhaengeLeeren()
    erwaehnungMerker.value = []
    erwaehnungSchliessen()
    erwaehnungUnterdrueckt.value = -1
    antwortAuf.value = null
    await nachUntenScrollen()
    // Liste (letzte Nachricht, Zähler) zieht nach — eine Abfrage, kein Raten.
    await laden()
    if (eingabeEl.value && typeof eingabeEl.value.focus === 'function') eingabeEl.value.focus()
  } catch (fehler) {
    // CHAT-7a: 403 im 1:1 = „nicht mehr erreichbar“ — dann weicht die
    // Eingabe dem ruhigen Hinweis (Karte Punkt 3), der Verlauf bleibt. Im
    // Gruppen-Chat bleibt es beim gewohnten Fehlertext (Karte UI-2 Punkt 2).
    const lage = sendeFehlerZustand(fehler, { direkt: istOffenesDirekt.value })
    if (lage.gesperrt) {
      sendenVonServerGesperrt.value = true
      eingabeFehler.value = ''
    } else {
      const zustand = fehlerZustand(fehler)
      eingabeFehler.value = zustand ? `${zustand.titel}. ${zustand.text}` : lage.text
    }
  } finally {
    sendet.value = false
  }
}

/** Antworten: die Zitatzeile über der Eingabe; Senden nimmt sie mit. */
function antworten(nachricht) {
  antwortAuf.value = nachricht
  if (eingabeEl.value && typeof eingabeEl.value.focus === 'function') eingabeEl.value.focus()
}

// ── Reaktionen, Bearbeiten, Löschen ────────────────────────────────────────

async function reaktionSetzen({ nachricht, reaktion }) {
  const neu = naechsteReaktion(nachricht.reaktionen, reaktion)
  try {
    const antwort = await apiCall('chat.reaktion_setzen', { nachricht: nachricht.ident, reaktion: neu })
    const stand = Array.isArray(antwort?.reaktionen) ? antwort.reaktionen : []
    nachrichten.value = nachrichten.value.map((n) => (n.ident === nachricht.ident ? { ...n, reaktionen: stand } : n))
  } catch (fehler) {
    const zustand = fehlerZustand(fehler)
    verlaufFehler.value = zustand ? `${zustand.titel}. ${zustand.text}` : fehlertext(fehler)
  }
}

const bearbeiten = ref(null)
const bearbeitenText = ref('')
const bearbeitenLaeuft = ref(false)
const bearbeitenFehler = ref('')

function bearbeitenOeffnen(nachricht) {
  bearbeiten.value = nachricht
  bearbeitenText.value = nachricht.text || ''
  bearbeitenFehler.value = ''
}

async function bearbeitenSpeichern() {
  const ziel = bearbeiten.value
  if (!ziel || bearbeitenLaeuft.value) return
  const pruefung = pruefeText(bearbeitenText.value)
  if (!pruefung.ok) {
    bearbeitenFehler.value = pruefung.fehler
    return
  }
  bearbeitenLaeuft.value = true
  try {
    const geaendert = await apiCall('chat.aendern', { nachricht: ziel.ident, text: pruefung.text })
    const zeile = verlaufsZeile(geaendert, { ich: ich.value })
    if (zeile) nachrichten.value = nachrichten.value.map((n) => (n.ident === ziel.ident ? { ...n, ...zeile } : n))
    bearbeiten.value = null
  } catch (fehler) {
    const zustand = fehlerZustand(fehler)
    bearbeitenFehler.value = zustand ? `${zustand.titel}. ${zustand.text}` : fehlertext(fehler)
  } finally {
    bearbeitenLaeuft.value = false
  }
}

async function loeschen(nachricht) {
  const ja = await bestaetigen({
    titel: 'Nachricht löschen?',
    text: 'Die Nachricht verschwindet für alle. Im Verlauf bleibt sichtbar, dass hier etwas gelöscht wurde.',
    aktion: 'Löschen',
    gefahr: true,
  })
  if (!ja) return
  try {
    const stand = await apiCall('chat.loeschen', { nachricht: nachricht.ident })
    const zeile = verlaufsZeile(stand, { ich: ich.value })
    if (zeile) nachrichten.value = nachrichten.value.map((n) => (n.ident === nachricht.ident ? { ...n, ...zeile } : n))
    await laden()
  } catch (fehler) {
    const zustand = fehlerZustand(fehler)
    verlaufFehler.value = zustand ? `${zustand.titel}. ${zustand.text}` : fehlertext(fehler)
  }
}

// ── Umfragen (CHAT-5-UI) ───────────────────────────────────────────────────

/**
 * Der Knopf „Umfrage starten“ hängt an `darfSenden` (oben) — derselbe Wert wie
 * das Eingabefeld, denn `umfrage_anlegen` verlangt dieselbe Aktion.
 */
const umfrageDialog = ref(false)
const umfrageAnlegenLaeuft = ref(false)
const umfrageAnlegenFehler = ref('')
/** Welche Umfrage gerade abgegeben wird (`name`) — sperrt nur deren Knopf. */
const umfrageLaeuft = ref('')
/** Meldungen je Umfrage (`name` → Text): 403, 400 („schon abgestimmt“) … */
const umfrageFehler = ref({})

/**
 * Eine Umfrage-Meldung ruhig an DIESER Karte anzeigen (keine Wand aus Text).
 *
 * `null`/`''` heißt ZURÜCKSETZEN — der Eintrag wird entfernt. Ohne diesen
 * Zweig setzte `fehlertext(null)` den Katalog-Standardtext („Das hat gerade
 * nicht geklappt …“) und die Meldung bliebe nach erfolgreicher Abstimmung
 * stehen (Befund DMB-525e1b2d4a0a).
 */
function umfrageFehlerSetzen(name, fehler) {
  if (!fehler) {
    if (!(String(name) in umfrageFehler.value)) return
    const rest = { ...umfrageFehler.value }
    delete rest[String(name)]
    umfrageFehler.value = rest
    return
  }
  const zustand = fehlerZustand(fehler)
  const text = zustand ? `${zustand.titel}. ${zustand.text}` : fehlertext(fehler)
  umfrageFehler.value = { ...umfrageFehler.value, [String(name)]: text }
}

/** Die Zähler einer Umfrage in den Verlauf übernehmen (ohne zweiten Abruf). */
function umfrageUebernehmen(umfrage) {
  if (!umfrage?.name) return
  nachrichten.value = nachrichten.value.map((n) => (n.umfrage?.name === umfrage.name
    ? { ...n, umfrage }
    : n))
}

/**
 * „Umfrage starten“ — die Antwort bringt die neue Nachricht samt Umfrage nur
 * als `{name, umfrage}` (ohne `text`), das reicht `verlaufsZeile` nicht: die
 * Zeile stünde bis zum nächsten Abruf als „gelöscht“ da. Deshalb den Verlauf
 * still neu laden — der Server liefert die fertige Hülle.
 */
async function umfrageAnlegen(daten) {
  const offen = offeneKennung.value
  if (!offen || umfrageAnlegenLaeuft.value) return
  umfrageAnlegenLaeuft.value = true
  umfrageAnlegenFehler.value = ''
  try {
    await apiCall('chat.umfrage_anlegen', {
      gespraech: offen,
      frage: daten.frage,
      optionen: daten.optionen,
      mehrfach: daten.mehrfach === true,
      anonym: daten.anonym !== false,
      frist: daten.frist || undefined,
    })
    umfrageDialog.value = false
    await verlaufLaden({ still: true })
    await nachUntenScrollen()
    await laden()
  } catch (fehler) {
    const zustand = fehlerZustand(fehler)
    umfrageAnlegenFehler.value = zustand ? `${zustand.titel}. ${zustand.text}` : fehlertext(fehler)
  } finally {
    umfrageAnlegenLaeuft.value = false
  }
}

/** Abstimmen oder ändern — der Server antwortet mit dem neuen Stand. */
async function umfrageAbstimmen({ umfrage, optionen }) {
  if (!umfrage?.name || umfrageLaeuft.value) return
  umfrageLaeuft.value = umfrage.name
  umfrageFehlerSetzen(umfrage.name, null)
  try {
    const stand = await apiCall('chat.umfrage_abstimmen', {
      umfrage: umfrage.name,
      optionen,
    })
    umfrageUebernehmen(stand)
  } catch (fehler) {
    umfrageFehlerSetzen(umfrage.name, fehler)
  } finally {
    umfrageLaeuft.value = ''
  }
}

/**
 * Schließen — der Server prüft das Recht; ein „Nein“ (403) bleibt ruhig.
 *
 * Die Sperre hält bis zur Antwort (`umfrageSchliessenLaeuft`): ein zweiter
 * Klick schickt keinen zweiten POST.
 */
const umfrageSchliessenLaeuft = ref('')
async function umfrageSchliessen({ umfrage }) {
  if (!umfrage?.name) return
  if (umfrageSchliessenLaeuft.value === umfrage.name) return
  umfrageSchliessenLaeuft.value = umfrage.name
  try {
    const stand = await apiCall('chat.umfrage_schliessen', { umfrage: umfrage.name })
    umfrageUebernehmen(stand)
    umfrageFehlerSetzen(umfrage.name, null)
  } catch (fehler) {
    umfrageFehlerSetzen(umfrage.name, fehler)
  } finally {
    umfrageSchliessenLaeuft.value = ''
  }
}

// ── Runden (CHAT-7b-UI) ────────────────────────────────────────────────────

/**
 * Der Eintritts-Hinweis für die Vorlage — der ROHE Stand (`eintrittHinweisRoh`)
 * ist das, was der Server zuletzt zur Sichtbarkeit gesagt hat.
 */
const eintrittHinweis = computed(() => eintrittHinweisRoh.value)

/**
 * Anlegen, Vorschlagen, Zustimmen/Ablehnen, Verlassen — die Seite sendet, die
 * Regeln stehen in `composables/nachrichtenRunden.mjs`. Kein zweiter Weg:
 * „Neue Runde“ ist der Dialog, „Person vorschlagen“ derselbe Personenbaustein,
 * und die Vorschlagszeile im Verlauf meldet nur ihren Klick.
 */
const rundeDialogOffen = ref(false)
const rundeAnlegenLaeuft = ref(false)
const rundeAnlegenFehler = ref('')

/** Die aufklappbare Teilnehmerliste im Rundenkopf (Karte Punkt 3). */
const RUNDE_TEILNEHMER_ID = 'chat-runde-teilnehmende'
const teilnehmerOffen = ref(false)
/**
 * Die Beteiligten einer Runde — aus `mitglieder: [{mitglied, anzeigename}]`
 * der Antwort von `chat.meine_gespraeche` (Vertrag Review R1 Punkt 4). Es wird
 * NICHTS nachgeschlagen (`rundenNamenHolen` ist gestrichen) und nie eine rohe
 * Kennung angezeigt.
 */
const rundenMitglieder = computed(() => rundenMitgliederAus(offenesGespraech.value))
/** „Person vorschlagen“ nur unter 8 Beteiligten (Zahl aus der Liste). */
const vorschlagenMoeglich = computed(() => darfVorschlagen(offenesGespraech.value))

/**
 * Die Runden-Aktionen für das „⋯“-Menü am HANDY (Review R1 Punkt 9) — dieselben
 * zwei Aktionen wie die Knöpfe am Desktop, im vorhandenen `DkAktionen`-Muster.
 * „Person vorschlagen“ fehlt, wenn die Runde voll ist (dieselbe Zahl).
 */
const rundenEintraege = computed(() => {
  const liste = []
  if (vorschlagenMoeglich.value) {
    liste.push({ key: 'vorschlagen', label: VORSCHLAG_KNOPF, icon: 'person-plus',
      disabled: verlassenLaeuft.value, aktion: vorschlagDialogOeffnen })
  }
  liste.push({ key: 'verlassen', label: VERLASSEN_KNOPF, icon: 'entfernen', gefahr: true,
    getrennt: true, disabled: verlassenLaeuft.value, aktion: rundeVerlassen })
  return liste
})

/** „Neue Runde“ öffnen — ein alter Fehlertext bleibt nicht stehen (Punkt 6). */
function rundeDialogOeffnen() {
  rundeAnlegenFehler.value = ''
  rundeDialogOffen.value = true
}

/**
 * `:ohne` für „Person vorschlagen“: ich selbst und alle aktiven Beteiligten
 * (Review R1 Punkt 5) — die Suche bietet niemanden an, der schon dabei ist.
 */
const vorschlagOhneListe = computed(() => vorschlagOhne(offenesGespraech.value, ich.value))

/** Ist der Vorschlag-Dialog offen? Beim Öffnen wird der alte Fehler geleert. */
function vorschlagDialogOeffnen() {
  vorschlagAnlegenFehler.value = ''
  vorschlagDialogOffen.value = true
}

/** „Neue Runde“ — `chat.runde_anlegen(titel, mitglieder)`, Mitglieder = die ANDEREN. */
async function rundeAnlegen({ titel: name, auswahl }) {
  if (rundeAnlegenLaeuft.value) return
  rundeAnlegenLaeuft.value = true
  rundeAnlegenFehler.value = ''
  try {
    const rumpf = rundeAnlegenRumpf({ titel: name, auswahl, ich: ich.value })
    const kopf = await apiCall('chat.runde_anlegen', rumpf)
    rundeDialogOffen.value = false
    await laden()
    // Direkt in die neue Runde: die Kennung kommt aus der Serverantwort.
    const kennungNeu = String(kopf?.name || '')
    if (kennungNeu) adresseSetzen(gespraechHash(kennungNeu), { ersetzt: false })
  } catch (fehler) {
    // Ruhig und ohne Unterschied „gesperrt“ / „nicht erreichbar“ — der Server
    // sagt es nicht, die Oberfläche erfindet nichts (Karte Punkt 1).
    rundeAnlegenFehler.value = fehlertext(fehler)
  } finally {
    rundeAnlegenLaeuft.value = false
  }
}

/** „Person vorschlagen“ — `chat.runde_vorschlagen(gespraech, mitglied)`. */
const vorschlagDialogOffen = ref(false)
const vorschlagAnlegenLaeuft = ref(false)
const vorschlagAnlegenFehler = ref('')

async function vorschlagSenden(person) {
  const offen = offeneKennung.value
  if (!offen || vorschlagAnlegenLaeuft.value || !person?.mitglied) return
  vorschlagAnlegenLaeuft.value = true
  vorschlagAnlegenFehler.value = ''
  try {
    await apiCall('chat.runde_vorschlagen', vorschlagRumpf(offen, person.mitglied))
    vorschlagDialogOffen.value = false
    await verlaufLaden({ still: true })
    await laden()
    await nachUntenScrollen()
  } catch (fehler) {
    vorschlagAnlegenFehler.value = fehlertext(fehler)
  } finally {
    vorschlagAnlegenLaeuft.value = false
  }
}

/** Welcher Vorschlag gerade beantwortet wird (`nachricht`) — sperrt nur dessen Knöpfe. */
const vorschlagLaeuft = ref('')
/** Meldungen je Vorschlagszeile (`nachricht` → Satz). */
const vorschlagFehler = ref({})

function vorschlagFehlerSetzen(kennung, fehler) {
  if (!fehler) {
    const rest = { ...vorschlagFehler.value }
    delete rest[String(kennung)]
    vorschlagFehler.value = rest
    return
  }
  const zustand = fehlerZustand(fehler)
  vorschlagFehler.value = {
    ...vorschlagFehler.value,
    [String(kennung)]: zustand ? `${zustand.titel}. ${zustand.text}` : fehlertext(fehler),
  }
}

/**
 * Zustimmen/Ablehnen an einer Vorschlagszeile: `chat.runde_zustimmen(vorschlag)`
 * bzw. `chat.runde_ablehnen(vorschlag)`. Die Kennung kommt aus
 * `system.vorschlag` — der Kennung des VORSCHLAGS, nicht der Zeile (Review R1
 * Punkt 1). Der Stand steht danach im Verlauf — der stille Abruf holt ihn.
 */
async function vorschlagAntworten(art, { vorschlag }) {
  const kennung = String(vorschlag || '').trim()
  if (!kennung || vorschlagLaeuft.value) return
  vorschlagLaeuft.value = kennung
  vorschlagFehlerSetzen(kennung, null)
  try {
    await apiCall(art === 'zustimmen' ? 'chat.runde_zustimmen' : 'chat.runde_ablehnen',
      stimmeRumpf(kennung))
    await verlaufLaden({ still: true })
    await laden()
  } catch (fehler) {
    vorschlagFehlerSetzen(kennung, fehler)
  } finally {
    vorschlagLaeuft.value = ''
  }
}

const vorschlagZustimmen = (ereignis) => vorschlagAntworten('zustimmen', ereignis)
const vorschlagAblehnen = (ereignis) => vorschlagAntworten('ablehnen', ereignis)

/** „Runde verlassen“ — Rückfrage (`gefahr: true`) und `chat.runde_verlassen`. */
const verlassenLaeuft = ref(false)
/** Fehler beim Verlassen: ruhiger Hinweis AM KOPF, nicht im Verlauf (Punkt 8). */
const verlassenFehler = ref('')
async function rundeVerlassen() {
  const offen = offeneKennung.value
  if (!offen || verlassenLaeuft.value) return
  const ja = await bestaetigen(verlassenFrage())
  if (!ja) return
  verlassenLaeuft.value = true
  verlassenFehler.value = ''
  try {
    await apiCall('chat.runde_verlassen', verlassenRumpf(offen))
    await laden()
    // Die Runde ist weg (kein Leserecht mehr): zurück zur Liste.
    adresseSetzen(BEREICH, { ersetzt: false })
    zuruecksetzen()
  } catch (fehler) {
    // NICHT in `verlaufFehler`: der ersetzt den ganzen Verlauf. Der Hinweis
    // steht am Rundenkopf, der gelesene Verlauf bleibt stehen.
    const zustand = fehlerZustand(fehler)
    verlassenFehler.value = zustand ? `${zustand.titel}. ${zustand.text}` : fehlertext(fehler)
  } finally {
    verlassenLaeuft.value = false
  }
}

// ── Melden (CHAT-6-UI) ─────────────────────────────────────────────────────

/**
 * „Melden“ an einer FREMDEN, nicht gelöschten Nachricht (Konzept 2.5).
 *
 * Die Blase bietet den Knopf/den Menüeintrag nur dort an (`meldbar`); hier
 * wird die gemeldete Nachricht für den Dialog gemerkt. Rechte prüft der
 * Server — ein „nein“ (403) kommt als ruhiger Text zurück.
 */
const meldeDialog = ref(false)
const meldeZiel = ref(null)
const meldeLaeuft = ref(false)
const meldeFehler = ref('')
/** Die Meldung ist eingegangen → der Dialog zeigt die Bestätigung. */
const meldeEingegangen = ref(false)

function meldenOeffnen(nachricht) {
  if (!darfMelden(nachricht)) return
  meldeZiel.value = nachricht
  meldeFehler.value = ''
  meldeEingegangen.value = false
  meldeDialog.value = true
}

/**
 * Absenden — `chat.meldung_senden(nachricht, grund, freitext)`.
 *
 * Antwort mit `meldung_offen`/`name` = eingegangen (ruhige Bestätigung im
 * Dialog). Ein Fehler des Servers steht an derselben Stelle, im Klartext des
 * Servers, wenn er brauchbar ist — die Antwort auf eine doppelte Meldung
 * („Diese Nachricht wurde von dir bereits gemeldet.“) ist genau das.
 */
async function meldungSenden({ grund, freitext }) {
  const ziel = meldeZiel.value
  if (!ziel || meldeLaeuft.value) return
  meldeLaeuft.value = true
  meldeFehler.value = ''
  try {
    const antwort = await apiCall('chat.meldung_senden', {
      nachricht: ziel.ident || ziel.name || ziel.id,
      grund,
      freitext: freitext || undefined,
    })
    const lage = meldeAntwort(antwort)
    if (!lage.ok) {
      meldeFehler.value = lage.text
      return
    }
    meldeEingegangen.value = true
  } catch (fehler) {
    // Der Satz des Servers bleibt stehen, wenn er eine Auskunft ist („Diese
    // Nachricht wurde von dir bereits gemeldet.“); sonst der Katalogtext.
    const zustand = fehlerZustand(fehler)
    let ersatz = ''
    if (zustand?.art === 'eingabe') ersatz = zustand.text
    else if (zustand?.art === 'kein-zugriff') ersatz = MELDUNG_KEIN_ZUGRIFF
    else ersatz = fehlertext(fehler)
    meldeFehler.value = meldeFehlerText(fehler, { ersatz })
  } finally {
    meldeLaeuft.value = false
  }
}

// ── Takt (Polling) ─────────────────────────────────────────────────────────

/** Ist der Tab sichtbar? (Nur dann darf gelesen und gefragt werden.) */
function tabSichtbar() {
  return typeof document === 'undefined' || document.hidden !== true
}

/**
 * Kurzes Polling (Karte Punkt 2): EIN Abruf von `meine_gespraeche` je Takt
 * (MUSS 4 — Liste und Zähler aus demselben Ergebnis) und der offene Verlauf,
 * ±10 s, NUR bei sichtbarem Tab. Kein WebSocket.
 *
 * MUSS 3 (Timer-Leck): Den Timer hält `taktGeber`, und der ist nach `anhalten`
 * GESTOPPT — der Aufbau wartet auf Antworten (`await laden()`), und kommt
 * `onUnmounted` dazwischen, öffnet ein spätes `starten()` keinen zweiten Timer
 * mehr. Hier steht deshalb KEIN eigenes `setInterval`/`setTimeout`.
 *
 * Backoff: nach einem Fehler wächst die Wartezeit (10 → 20 → 40 → 60 s). Der
 * Rückgabewert des Abrufs trägt sie (`dauer`), der Takt plant damit den
 * nächsten Termin; der erste Erfolg setzt auf den Grundtakt zurück.
 */
let fehlschlaege = 0

async function taktAbruf() {
  if (!aktivSeite || !modulAn.value) return undefined
  let erfolg = await laden({ still: true })
  // CHAT-3c-2 (Review R1, MUSS 1): der Takt fragt den Verlauf, solange rechts
  // ein Gespräch offen ist — `offeneKennung`, nicht `kennung` (das ist während
  // einer Suche leer).
  if (aktivSeite && erfolg && offeneKennung.value) {
    // CHAT-3a-3/B: OHNE `seit` — die volle neueste Seite (`richtung:
    // 'neueste'`). `seit` trug nur Nachrichten mit späterem Zeitstempel und
    // liess Bearbeitungen, Löschungen, Reaktionen und Lesestände sichtbarer
    // Zeilen aus. Die Zusammenführung leistet `seiteEinordnen` (bekannte
    // Zeilen ersetzen, neue hinten anhängen, `aktualisiert` zählen).
    const geladen = await verlaufLaden({ still: true })
    erfolg = geladen || erfolg
  }
  fehlschlaege = erfolg ? 0 : fehlschlaege + 1
  return { dauer: fehlschlaege ? backoffMs(fehlschlaege) : TAKT_MS }
}

const takt = taktGeber({
  takt: TAKT_MS,
  abfragen: taktAbruf,
  sichtbar: tabSichtbar,
  sichtbarkeitBeobachten: (fn) => {
    if (typeof document === 'undefined') return () => {}
    document.addEventListener('visibilitychange', fn)
    return () => document.removeEventListener('visibilitychange', fn)
  },
})

/**
 * Stand des Takts und der Suche — für den Node-Test nachlesbar, ohne etwas zu
 * raten. Kein Betriebsweg.
 *
 * CHAT-3c (Review R1): `defineExpose` auf Modulebene wirkt in `<script setup>`
 * NICHT (es gehört in den Setup-Körper) — die Werte waren von außen nie
 * erreichbar. Über die laufende Instanz herausgegeben ist es EINE Stelle.
 */
function taktStand() {
  return {
    aktiv: aktivSeite,
    gestartet: takt.istGestartet(),
    gestoppt: takt.istGestoppt(),
    fehlschlaege,
    ...takt.stand(),
  }
}

// ── CHAT-11b: Sprung zur Nachricht und Suche im Gespräch ───────────────────

/**
 * Der Weg zu einer Nachricht ist der der Erwähnungs-Glocke (CHAT-9b):
 * `chat.nachricht_kontext(nachricht)` sagt, in welchem Gespräch sie steht —
 * dieselbe Auskunft, dieselbe Adresse (`#/nachrichten/<kennung>`), KEIN
 * zweiter Weg. `erwaehnungZiel` verpackt genau das (`glockenziele.mjs`) und
 * antwortet bei unbekannter/gelöschter/fremder Nachricht mit dem Bereich.
 */
async function kontextHolen(nachricht) {
  const ziel = String(await erwaehnungZiel({ document_name: nachricht }, apiGet) || '')
  const kennung = ziel.startsWith(`${BEREICH}/`) ? ziel.slice(BEREICH.length + 1) : ''
  return kennung ? { gespraech: decodeURIComponent(kennung) } : null
}

/** Die Kennung der Nachricht, zu der gesprungen werden soll — `''` = keine. */
const sprungNachricht = ref('')
/**
 * Das Gespräch, in dem die gesprungene Nachricht steht (Review R1/1) — leer,
 * solange der Server es noch nicht gesagt hat oder der Sprung keines kennt.
 * `sprungAusfuehren` löst ihn ein, sobald GENAU DIESES Gespräch offen ist.
 */
const sprungGespraech = ref('')
/** Wie viele Ladeversuche dieser Sprung schon gemacht hat (Karte: ≤ 10). */
const sprungSeiten = ref(0)
/**
 * Die LAUFNUMMER des aktuellen Sprungs. Jeder `springen` zählt sie hoch;
 * jede Schleife merkt sich ihre Nummer und gibt nach JEDEM `await` auf, wenn
 * sie nicht mehr die jüngste ist (oder die Seite abgebaut wurde). Damit kann
 * kein alter Lauf einen neuen Sprung (oder den Hinweis eines inzwischen
 * abgebrochenen) überschreiben.
 *
 * CHAT-11b-3/2: Die Sperre hängt an DIESER Nummer — ein Wechsel in ein
 * drittes Gespräch entwertet den alten Lauf (`sprungLaufNr += 1`), und ein
 * neuer Sprung darf sofort starten, statt auf die hängende Antwort des alten
 * zu warten. Ein bloßes Bool konnte das nicht (es blieb true, bis die alte
 * Antwort kam).
 */
let sprungLaufNr = 0
/**
 * Läuft gerade ein Nachladen für einen Sprung? Wird nur noch zusammen mit
 * `sprungLaufNr` gepflegt: `sprungBeginnen` setzt true, `sprungBeenden` (nur
 * für den JÜNGSTEN Lauf) und die Abbruchstellen setzen false. Die eigentliche
 * Sperre ist die Laufnummer (`sprungGilt`).
 */
let sprungLaeuft = false
/** Die Nummer, die ein abgebrochener Sprung hinterlässt — s. `sprungAbbrechen`. */
function sprungGilt(nr) {
  return aktivSeite && nr === sprungLaufNr
}

/**
 * CHAT-11b-3/2: Einen Sprung beginnen — entwertet einen laufenden (er darf
 * danach nichts mehr schreiben) und gibt die neue Laufnummer zurück. Damit
 * startet ein neuer Sprung SOFORT, auch wenn der alte noch in einer Antwort
 * hängt.
 */
function sprungBeginnen() {
  sprungLaufNr += 1
  sprungLaeuft = true
  sprungSeiten.value = 0
  // CHAT-11b-4/1: Das ZIEL des verdrängten Laufs fällt hier weg — es gehörte
  // dem alten Lauf, und ein neuer ist noch nicht einmal gefragt. Endete er
  // ohne Gespräch (`art === 'nichts'` / `'weg'`), stünde es sonst weiter da,
  // würde beim nächsten Aufbau eingelöst und trüge den Hinweis „gibt es nicht
  // mehr“ für eine Nachricht, zu der niemand mehr wollte.
  //
  // Anmerkung (Handoff CHAT-11b-4): Im heute erreichbaren Ablauf räumt schon
  // der Zweig `'nichts'`/`'weg'` in `springen` (über `sprungAbbrechen`) bzw.
  // `sprungAusfuehren` das Ziel; ein Test, der NUR diese Zeilen entfernt,
  // bleibt darum grün (Gegenprobe gefahren). Die Räumung bleibt als zweite
  // Sicherung stehen — sie kostet nichts und deckt den Fall ab, dass ein
  // späterer Zweig das Aufräumen vergisst.
  sprungNachricht.value = ''
  sprungGespraech.value = ''
  // … und der Hinweis des verdrängten Laufs ebenso: er gehörte zu einer
  // Nachricht, die diesen Sprung nicht mehr angeht.
  sprungHinweis.value = ''
  return sprungLaufNr
}

/**
 * Die Sperren zeigen beim Start — `{ laeuft: boolean, nr: number }`. Der Node-
 * Test braucht beides, weil `sprungFertig` bei falscher Sperre sonst einfach
 * SOFORT auflöst statt zu hängen (und damit grün aussähe).
 */
function sprungSperreStand() {
  return { laeuft: sprungLaeuft, nr: sprungLaufNr }
}

/**
 * Der Lauf `nr` ist vorbei — Sperre fällt und die Wartenden (`sprungFertig`)
 * werden aufgelöst, wenn dieser Lauf noch der JÜNGSTE ist. Ein entwerteter
 * Lauf löst hier NICHTS: seine Wartenden hat schon der Abbruch entlassen
 * (`zuruecksetzen`, `sprungAbbau`), und die eines neueren Laufs gehören ihm
 * nicht.
 */
function sprungBeenden(nr) {
  if (nr !== sprungLaufNr) return
  sprungLaeuft = false
  sprungAbschliessen()
}

/**
 * Review R1/1: bricht den laufenden Sprung STILL ab. Das Ziel fällt weg, ohne
 * Hinweis — es gibt für die lesende Person nichts zu erfahren (sie hat in ein
 * anderes Gespräch gewechselt). Die Abbruchbedingung bleibt: eine Schleife, die
 * noch auf eine Antwort wartet, prüft danach `sprungGilt(nr)`.
 */
function sprungAbbrechen() {
  sprungNachricht.value = ''
  sprungGespraech.value = ''
  sprungSeiten.value = 0
}

/**
 * Review R1/5: Die Seite wird abgebaut — ein laufender Sprung endet mit ihr
 * (die Laufnummer entwertet jede wartende Schleife, `sprungAbschliessen` löst
 * die Wartenden auf). Danach schreibt niemand mehr in einen toten Zustand.
 */
function sprungAbbau() {
  if (!sprungLaeuft) return
  sprungLaufNr += 1
  sprungLaeuft = false
  sprungAbbrechen()
  sprungAbschliessen()
}

/** Löst auf, wenn der laufende Sprung (Nachladen + Rollen) fertig ist. */
let sprungWartende = []
function sprungAbschliessen() {
  const offen = sprungWartende
  sprungWartende = []
  for (const loese of offen) loese()
}
const sprungFertig = () => new Promise((loese) => {
  if (!sprungLaeuft) { loese(); return }
  sprungWartende.push(loese)
})
/** Der ruhige Hinweis „gibt es nicht mehr“ — steht im Verlauf. */
const sprungHinweis = ref('')
/** Kurz hervorgehobene Nachricht (Kennung) — fällt nach ein paar Sekunden. */
const markierteNachricht = ref('')
let markierTimer = null

/**
 * Eine Nachricht kurz hervorheben — wie es der Sprung braucht. Der Timer läuft
 * nur, solange die SEITE lebt (`onUnmounted` räumt ihn ab) und setzt danach
 * nichts mehr.
 */
function nachrichtMarkieren(kennung, { still = false } = {}) {
  const k = String(kennung || '').trim()
  if (!k) return
  if (markierTimer) clearTimeout(markierTimer)
  markierteNachricht.value = k
  markierTimer = setTimeout(() => {
    markierTimer = null
    if (!aktivSeite) return
    markierteNachricht.value = ''
  }, still ? 4000 : 2500)
}

/** Die Abfrage des Verlaufs, die gerade läuft (oder `null`) — `oeffnen` merkt
 *  sie, damit der Sprung auf sie WARTEN kann statt zu raten. */
let offenLaeuft = null

/**
 * Der Sprung: Nachricht → Gespräch → Nachricht. Der EINE Weg, den auch die
 * Glocke nimmt.
 *
 *   1. Auskunft des Servers (`sprungZiel` → `chat.nachricht_kontext`).
 *      Unbekannt oder kein Leserecht → Bereich „Nachrichten“, keine geratene
 *      Kennung.
 *   2. Das Ziel im Modul merken (`sprungNachricht`, `sprungGespraech`) und das
 *      Gespräch über die ADRESSE öffnen. Review R1/1: `navigate`/`adresseSetzen`
 *      liest die Adresse zwar sofort nach, `oeffnen` läuft aber asynchron über
 *      mehrere Antworten. Darum läuft der Sprung NICHT hier weiter, sondern in
 *      `sprungAusfuehren` — das wartet, bis genau DIESES Gespräch offen ist.
 *   3. Steht die Nachricht noch nicht im geladenen Verlauf, ältere Seiten
 *      nachladen (höchstens `SPRUNG_MAX_SEITEN`), dann kurz hervorheben.
 *   4. Ist sie nicht mehr da (gelöscht), steht der ruhige Hinweis da — an einer
 *      Stelle, die auch die LISTENANSICHT zeigt (R1/6).
 */
async function springen(nachricht) {
  const kennung = String(nachricht?.nachricht || nachricht || '').trim()
  if (!kennung) return
  const nr = sprungBeginnen()
  sprungHinweis.value = ''
  try {
    const ziel = await sprungZiel(kennung, kontextHolen, nachrichtenAdresse)
    if (!sprungGilt(nr)) return
    if (ziel.art === 'nichts') {
      // Keine Auskunft: der Bereich ist das ehrliche Ziel (wie bei der Glocke).
      navigate(nachrichtenAdresse())
      return
    }
    sprungNachricht.value = kennung
    sprungGespraech.value = ziel.art === 'gespraech' ? String(ziel.gespraech || '') : ''
    if (ziel.art === 'weg') {
      // Die Nachricht gibt es nicht mehr — Gespräch öffnen (wenn der Server
      // eines genannt hat, hier: keines) und den ruhigen Satz zeigen.
      sprungHinweis.value = WEG_TEXT
      sprungNachricht.value = ''
      return
    }
    // Handy (R1/4): Mit einem Sprung endet die Suche — sonst bliebe die
    // Trefferfläche die sichtbare Spalte und der Verlauf verborgen.
    const adresse = handySucheSchliessen(ziel.adresse)
    const schonOffen = String(offeneKennung.value || '') === String(ziel.gespraech || '')
      && !sucheOffen.value
    if (!schonOffen || adresse !== aktuellerHash()) navigate(adresse)
    await sprungAusfuehren(nr)
  } finally {
    sprungBeenden(nr)
  }
}

/** Die Adresse, wie sie gerade in der Adresszeile steht. */
function aktuellerHash() {
  return typeof window === 'undefined' ? '' : String(window.location.hash || '')
}

/**
 * Handy (Review R1/4): Ein Sprung in ein Gespräch schließt die Suche. Am
 * Handy ist die Suchspalte die sichtbare — bliebe sie offen, stünde der
 * Verlauf, zu dem gesprungen wurde, hinter ihr. Am Desktop ändert sich
 * nichts: dort schließt der Sprung die Suche NICHT (zwei Spalten, die Suche
 * bleibt links stehen).
 */
function handySucheSchliessen(adresse) {
  const ziel = String(adresse || '')
  if (istHandyLage.value !== true || !sucheOffen.value) return ziel
  const gespraech = String(new URL(ziel, 'https://x.invalid').hash || ziel).replace(/^#/, '')
  const rein = gespraech.split('?')[0]
  if (rein === SUCH_HASH) return ziel
  // Die Suche wird verlassen: Feld und Trefferfläche zu (die SEITE räumt den
  // Begriff beim nächsten Lesen der Adresse ohnehin ab).
  sucheOffen.value = false
  suchBegriff.value = ''
  return ziel
}

/**
 * Warten, bis das gesprungene Gespräch offen und sein Verlauf da ist.
 * `true` = es kann weitergehen. Review R1/1: Ohne offenes Gespräch oder mit
 * einem ANDEREN offenen Gespräch darf nichts geladen werden (vorher landeten
 * ältere Seiten des ALTEN Gesprächs im Verlauf).
 */
async function sprungBereit(nr) {
  // CHAT-11b-2/3: Die Warteschleife auf die Adresse (der `hashchange` des
  // Browsers kommt als eigener Task) hat eine EIGENE Obergrenze — ein
  // Adresswechsel, der nie kommt, lässt den Sprung nicht hängen. Ein Abbruch
  // (Decke, abgebaute Seite, anderes Gespräch) ist still: kein Hinweis.
  const grenze = Date.now() + SPRUNG_ADRESSE_MS
  for (;;) {
    if (!sprungGilt(nr)) return false
    const ziel = String(sprungGespraech.value || '')
    const jetzt = String(offeneKennung.value || '')
    if (ziel && jetzt !== ziel) {
      // Ein anderes Gespräch ist offen (noch nicht gewechselt oder inzwischen
      // ein drittes): warten bzw. aufgeben — aber nie dessen Seiten laden.
      if (jetzt) {
        // Steht in der Adresse inzwischen das ZIEL, ist der Wechsel nur noch
        // nicht durch (hashchange als eigener Task) — dann warten.
        if (!wartetAufAdresse(ziel)) return false
        if (ueberDecke(grenze)) return false
        await new Promise((loese) => setTimeout(loese, 0))
        continue
      }
      await nextTick()
      if (String(offeneKennung.value || '') === ziel) continue
      // Die Adresse steht noch nicht im Modul (hashchange kam noch nicht).
      if (!wartetAufAdresse(ziel)) return false
      if (ueberDecke(grenze)) return false
      await new Promise((loese) => setTimeout(loese, 0))
      continue
    }
    // Offen (oder gar kein Gespräch verlangt): den Verlauf abwarten, falls er
    // gerade geholt wird.
    if (offenLaeuft) { await offenLaeuft.catch(() => {}); continue }
    if (geoeffnet.value !== (ziel || geoeffnet.value)) return false
    return true
  }
}

/** Ist die Wartefrist auf die Adresse abgelaufen? (ohne Hinweis, s. `sprungBereit`) */
function ueberDecke(grenze) {
  return Date.now() > grenze
}

/**
 * Steht das Ziel in der Adresse, während das Modul es noch nicht kennt?
 * (Der `hashchange` des Browsers kommt als eigener Task — genau der Fall aus
 * Review R1/1.) Ein `#/nachrichten/<sonstiges>` ist es NICHT: dann ist ein
 * anderes Gespräch gewollt.
 */
function wartetAufAdresse(ziel) {
  if (!ziel) return false
  const pfad = aktuellerHash()
  if (pfad.split('?')[0] === SUCH_HASH) return false
  return pfad === `#${nachrichtenAdresse(ziel)}` || pfad === nachrichtenAdresse(ziel)
}

/**
 * Den Verlauf nachladen, bis die gesprungene Nachricht da ist — oder die
 * Versuche aufgebraucht sind. Die Entscheidung steht in `sprungSchritt`
 * (DOM-frei prüfbar); hier wird sie ausgeführt.
 *
 * Review R1/1: `nr` ist die Laufnummer des Sprungs (`springen`). Nach JEDEM
 * `await` wird geprüft, ob er noch gilt — sonst hat inzwischen ein Wechsel
 * (oder der Abbau) den Sprung beendet, und ein spätes `sprungSchritt({nachricht:
 * ''})` schriebe den falschen „gibt es nicht mehr“-Satz in ein FREMDES
 * Gespräch. Abbruch ist immer still.
 */
async function sprungAusfuehren(nr) {
  if (!sprungNachricht.value) return
  if (!(await sprungBereit(nr))) {
    // Kein gültiger Sprung mehr: nichts laden, nichts behaupten.
    if (!sprungGilt(nr)) return
    // Review R1/4: Am Ziel angekommen, aber sein Verlauf ist nicht da (Öffnen
    // gescheitert, `geoeffnet` blieb leer) — dann fällt das Ziel weg, statt
    // beim nächsten Aufbau als halber Sprung stehen zu bleiben.
    if (String(offeneKennung.value || '') === String(sprungGespraech.value || '')) {
      sprungAbbrechen()
    }
    return
  }
  for (;;) {
    if (!sprungGilt(nr)) return
    const lauf = sprungSchritt({
      nachricht: sprungNachricht.value,
      vorhanden: nachrichten.value,
      gespraech: sprungGespraech.value,
      offen: offeneKennung.value,
      seiten: sprungSeiten.value,
    })
    sprungSeiten.value = lauf.seiten
    if (lauf.schritt === 'da') {
      const kennung = sprungNachricht.value
      sprungHinweis.value = ''
      sprungNachricht.value = ''
      sprungGespraech.value = ''
      await zurNachrichtScrollen(kennung)
      if (!sprungGilt(nr)) return
      nachrichtMarkieren(kennung)
      return
    }
    if (lauf.schritt === 'weg') {
      sprungHinweis.value = WEG_TEXT
      sprungAbbrechen()
      return
    }
    if (lauf.schritt === 'wechsel') {
      // Ein anderes Gespräch ist offen (geworden): still aufgeben.
      sprungAbbrechen()
      return
    }
    if (lauf.schritt === 'laden') {
      // Leerer Verlauf: erst die neueste Seite — auch dieser Versuch zählt
      // gegen `SPRUNG_MAX_SEITEN` (R1/5).
      const geladen = await verlaufLaden()
      if (!sprungGilt(nr)) return
      const erreicht = geladen || geoeffnet.value === offeneKennung.value
      // Ein Wechsel während des Ladens ist kein „gibt es nicht mehr“.
      if (String(offeneKennung.value || '') !== String(sprungGespraech.value || '')) {
        sprungAbbrechen()
        return
      }
      if (!erreicht || !nachrichten.value.length) {
        // Antwort ohne Zeilen: mehr kommt nicht.
        sprungHinweis.value = WEG_TEXT
        sprungAbbrechen()
        return
      }
      continue
    }
    // 'weiter': eine ältere Seite.
    //
    // Review R1/1: Erst prüfen, ob überhaupt noch das ZIEL offen ist — der
    // Wechsel kann den Sprung während des vorigen `await` erwischt haben.
    if (String(offeneKennung.value || '') !== String(sprungGespraech.value || '')) {
      sprungAbbrechen()
      return
    }
    // CHAT-11b-2/2 + Review R1/2: Läuft für DIESES Gespräch schon ein
    // Nachladen (Scroll), wird darauf gewartet, ohne zu zählen; danach wird
    // NEU entschieden (die Seite kann die Nachricht schon enthalten, ein
    // Fehlschlag ist kein „weg“).
    if (aelterLaeuftIn(sprungGespraech.value)) {
      await aelterWarten(sprungGespraech.value)
      if (!sprungGilt(nr)) return
      continue
    }
    const vorher = sprungAnker(nachrichten.value)
    const geladen = await aeltereLaden({ ohnePosition: true })
    if (!sprungGilt(nr)) return
    if (!geladen) {
      // Das Gespräch hat gewechselt (oder der Verlauf ließ sich nicht laden):
      // hier ist nichts behauptet — still aufgeben bzw. neu entscheiden.
      if (!sprungNachricht.value) return
      if (String(offeneKennung.value || '') !== String(sprungGespraech.value || '')) {
        sprungAbbrechen()
        return
      }
      const gefunden = nachrichten.value.some((n) => n.ident === sprungNachricht.value)
      if (!gefunden && sprungAnker(nachrichten.value) === vorher) {
        sprungHinweis.value = WEG_TEXT
        sprungAbbrechen()
        return
      }
    }
  }
}

/** Zur Nachricht rollen und sie holen — im eigenen Scrollkasten des Verlaufs. */
async function zurNachrichtScrollen(kennung) {
  await nextTick()
  const el = verlaufEl.value
  if (!el || typeof el.querySelector !== 'function') return
  const zeile = el.querySelector(`[data-name="${CSS_escape(kennung)}"]`)
  if (!zeile) return
  if (typeof zeile.scrollIntoView === 'function') {
    try { zeile.scrollIntoView({ block: 'center' }) } catch { /* egal */ }
  }
}

/** Ein Bezeichner für einen CSS-Attributwert (Kennungen tragen „-“ und „_“). */
function CSS_escape(wert) {
  return String(wert || '').replace(/["\\]/g, '\\$&')
}

// ── Suche im offenen Gespräch (Karte Punkt 3) ─────────────────────────────

const gespraechSucheOffen = ref(false)
const gespraechSucheBegriff = ref('')
const gespraechTreffer = ref([])
const gespraechSucheLaedt = ref(false)
const gespraechSucheFehler = ref('')
const gespraechSucheMehr = ref(false)
const gespraechSucheVor = ref('')
const gespraechTrefferAktiv = ref(0)
const gespraechSuchFeld = ref(null)
const GESPRAECH_TREFFER_LISTE = 'dk-gespraech-treffer'
/**
 * Review R1/7: Die Gesprächssuche arbeitet mit DENSELBEN Mitteln wie die
 * globale Suche — laufende Nummer (nur die jüngste Antwort schreibt) und ein
 * echter Abbruch des überholten Netzaufrufs.
 */
const gespraechLauf = laufNummer()
let gespraechAbort = null

function abbrechen() {
  if (!gespraechAbort) return
  try { gespraechAbort.abort() } catch { /* ein toter Abbruch darf nichts blocken */ }
  gespraechAbort = null
}

const gespraechSuchBremse = entpreller({
  beiFaelligkeit: (gefragt) => gespraechTrefferHolen(gefragt),
})

/** Der Kopf-Suchknopf öffnet das Feld; Escape schließt Liste und Feld. */
function gespraechSucheUmschalten() {
  gespraechSucheOffen.value = !gespraechSucheOffen.value
  if (!gespraechSucheOffen.value) {
    gespraechSucheZuruecksetzen()
    return
  }
  nextTick(() => {
    const el = gespraechSuchFeld.value
    if (el && typeof el.focus === 'function') el.focus()
  })
}

/**
 * Die Fläche der Gesprächssuche leeren.
 *
 * `beenden` gibt es hier NICHT: der Entpreller wird einmal gebaut und lebt so
 * lange wie die Seite — `beenden()` machte ihn für immer stumm (`tippen`
 * kehrte danach sofort um), und die Suche im Gespräch ginge nach dem ersten
 * Schließen nie wieder auf. Was hier endet, ist der OFFENE TERMIN.
 */
function gespraechSucheZuruecksetzen() {
  gespraechSuchBremse.abbrechen()
  gespraechLauf.abbrechen()
  abbrechen()
  gespraechSucheBegriff.value = ''
  gespraechTreffer.value = []
  gespraechSucheLaedt.value = false
  gespraechSucheFehler.value = ''
  gespraechSucheMehr.value = false
  gespraechSucheVor.value = ''
  gespraechTrefferAktiv.value = 0
}

/** Neuer Tastendruck im Gesprächsfeld: entprellt, mit `gespraech=<kennung>`. */
function gespraechSucheTippen(wert) {
  gespraechSucheBegriff.value = String(wert ?? '')
  gespraechLauf.abbrechen()
  abbrechen()
  gespraechTreffer.value = []
  gespraechSucheMehr.value = false
  gespraechSucheVor.value = ''
  gespraechSucheFehler.value = ''
  gespraechTrefferAktiv.value = 0
  if (!darfTrefferFragen(wert)) {
    gespraechSuchBremse.abbrechen()
    return
  }
  gespraechSuchBremse.tippen(String(wert ?? ''))
}

/**
 * Die Treffer im EINEN Gespräch — `gespraech=<kennung>` geht mit, sonst wäre
 * das eine Suche über alle Gespräche.
 *
 * Review R1/2: Der Begriff geht NUR GETRIMMT hinaus (`frageParameter`) — der
 * Server stammt selbst, ein gefaltetes „mueller“ fände kein „Müller“.
 * Review R1/7: Dieselbe Ordnung wie in der globalen Suche — laufende Nummer
 * (`gespraechLauf`, nur die jüngste Antwort schreibt) und ein echter
 * `AbortController` (der überholte Netzaufruf wird abgebrochen).
 */
async function gespraechTrefferHolen(gefragt, { vor = '' } = {}) {
  const gespraech = offeneKennung.value
  if (!gespraech || !aktivSeite) return
  if (!darfTrefferFragen(gefragt)) return
  if (!darfTrefferAntwort(gefragt, gespraechSucheBegriff.value)) return
  const nummer = gespraechLauf.neu()
  abbrechen()
  const steuerung = (typeof AbortController === 'function') ? new AbortController() : null
  gespraechAbort = steuerung
  gespraechSucheLaedt.value = true
  gespraechSucheFehler.value = ''
  try {
    const parameter = frageParameter(gefragt, { gespraech, vor })
    if (steuerung) parameter.signal = steuerung.signal
    const antwort = await apiGet('chat.nachrichten_suchen', parameter)
    if (!aktivSeite || !gespraechLauf.gilt(nummer)) return
    if (gespraech !== offeneKennung.value) return
    if (!darfTrefferAntwort(gefragt, gespraechSucheBegriff.value)) return
    const seite = trefferAusAntwort(antwort)
    gespraechTreffer.value = vor ? seiteAnhaengen(gespraechTreffer.value, seite.zeilen) : seite.zeilen
    gespraechSucheMehr.value = seite.mehr
    gespraechSucheVor.value = seite.vor
    gespraechTrefferAktiv.value = Math.min(gespraechTrefferAktiv.value,
      Math.max(0, gespraechTreffer.value.length - 1))
  } catch (f) {
    if (!aktivSeite || !gespraechLauf.gilt(nummer)) return
    if (f && (f.name === 'AbortError' || f.abgebrochen === true)) return
    if (gespraech !== offeneKennung.value) return
    // Seite 2 gescheitert: Seite 1 bleibt stehen (wie in der globalen Suche).
    if (!vor) {
      gespraechTreffer.value = []
      gespraechSucheMehr.value = false
      gespraechSucheVor.value = ''
    }
    gespraechSucheFehler.value = fehlertext(f, { text: 'Im Gespräch konnte nicht gesucht werden. Versuche es noch einmal.' })
  } finally {
    if (aktivSeite && gespraechLauf.gilt(nummer)) {
      gespraechSucheLaedt.value = false
      gespraechAbort = null
    }
  }
}

function gespraechMehrHolen() {
  if (!gespraechSucheMehr.value || !gespraechSucheVor.value || gespraechSucheLaedt.value) return
  gespraechTrefferHolen(gespraechSucheBegriff.value, { vor: gespraechSucheVor.value })
}

/** Ein Treffer im Gespräch: NICHT neu öffnen — wir sind schon drin. */
async function gespraechTrefferWaehlen(zeile) {
  if (!zeile) return
  const kennung = String(zeile.nachricht || '')
  await gespraechNachrichtSuchen(kennung)
}

/**
 * Dieselbe Nachlade-Regel wie beim Sprung — nur ohne Adresswechsel.
 *
 * CHAT-11b-3/1: Hier wird eine EIGENE Laufnummer gezogen und an
 * `sprungAusfuehren(nr)` übergeben. Ohne sie ist `sprungGilt(undefined)` immer
 * falsch: `sprungBereit` sagt sofort „nicht bereit“, der Sprung steigt aus, und
 * der Klick auf einen Suchtreffer tat nichts (und ließ das Ziel verwaist
 * stehen).
 *
 * CHAT-11b-3/2: Die Sperre hängt an der Laufnummer, nicht an einem Bool — ein
 * zweiter Klick entwertet den ersten und startet SOFORT (`sprungBeginnen`),
 * statt hinter dessen hängender Antwort zu warten.
 */
async function gespraechNachrichtSuchen(kennung) {
  const ziel = String(kennung || '').trim()
  if (!ziel) return
  const nr = sprungBeginnen()
  sprungHinweis.value = ''
  sprungNachricht.value = ziel
  sprungGespraech.value = String(offeneKennung.value || '')
  try {
    await sprungAusfuehren(nr)
  } finally {
    // CHAT-11b-4/2: Trifft der `finally` einen VERDRÄNGTEN Lauf, räumt er eine
    // Suchfläche, die er nicht MEHR besitzt: `gespraechTrefferSchliessen`
    // räumt Begriff und Treffer weg und schließt die Suche, die inzwischen neu
    // geöffnet wurde. Ein verdrängter Lauf darf seine (längst geschlossene)
    // Trefferliste höchstens noch abbrechen — nichts, was danach kommt.
    if (sprungGilt(nr)) gespraechTrefferSchliessen()
    else {
      gespraechSuchBremse.abbrechen()
      gespraechLauf.abbrechen()
    }
    sprungBeenden(nr)
  }
}

/** Tastatur in der Trefferliste des Gesprächs (Karte: Pfeile, Enter, Escape). */
function gespraechTrefferTaste(ereignis) {
  const absicht = trefferTaste({
    key: ereignis.key,
    isComposing: ereignis.isComposing === true,
    anzahl: gespraechTreffer.value.length,
  })
  if (!absicht) return
  ereignis.preventDefault()
  if (absicht === 'schliessen') {
    gespraechTrefferSchliessen()
    return
  }
  if (absicht === 'oeffnen') {
    const zeile = gespraechTreffer.value[Math.min(gespraechTrefferAktiv.value, gespraechTreffer.value.length - 1)]
    if (zeile) gespraechTrefferWaehlen(zeile)
    return
  }
  gespraechTrefferAktiv.value = naechsteTrefferStelle(
    gespraechTrefferAktiv.value,
    absicht === 'weiter' ? 1 : -1,
    gespraechTreffer.value.length,
  )
}

/** Escape: die Liste zu, das Feld auch (Karte Punkt 3). */
function gespraechTrefferSchliessen() {
  gespraechSuchBremse.abbrechen()
  gespraechLauf.abbrechen()
  abbrechen()
  gespraechSucheOffen.value = false
  gespraechSucheZuruecksetzen()
}

// CHAT-3c-2: `defineExpose` gehört in den Setup-Körper (hier ist er) — die
// Werte sind damit von außen lesbar, ohne die laufende Instanz zu verbiegen.
// `taktAbrufen` ruft einen Takt VON HAND ab (nur für den Node-Test: dort
// steht der Timer nie, „läuft der Takt weiter?“ wäre sonst nicht prüfbar) —
// mit derselben Sperre wie `takt.jetzt`: kein zweiter Lauf neben einem
// laufenden, kein Lauf vor Ablauf der Wartezeit.
defineExpose({
  taktStand,
  sucheStand,
  taktAbrufen: (augenblick) => takt.jetzt(augenblick),
  // CHAT-11b: Sprung und Gesprächssuche — für den Node-Test nachlesbar.
  // `sprungFertig` löst auf, wenn das Nachladen (und das Rollen) durch ist:
  // die Nachladungen laufen asynchron über mehrere Antworten, und ein Test
  // kann darauf nicht raten.
  sprungFertig,
  springen,
  // CHAT-11b-4/3: der Stand der Sperren (`laeuft`, `nr`) — s. `sprungSperreStand`.
  sprungSperre: sprungSperreStand,
  // Review R1/2: das Nachladen nach oben von Hand auslösen (der Scroll-Weg des
  // Verlaufs ist DOM-abhängig; hier zählt, was die Seite damit tut).
  aeltereLaden,
  sprungStand: () => ({
    nachricht: sprungNachricht.value,
    gespraech: sprungGespraech.value,
    seiten: sprungSeiten.value,
    hinweis: sprungHinweis.value,
    markiert: markierteNachricht.value,
  }),
  gespraechSuche: {
    umschalten: gespraechSucheUmschalten,
    tippen: gespraechSucheTippen,
    holen: (q, opts) => gespraechTrefferHolen(q, opts),
    mehr: gespraechMehrHolen,
    waehlen: gespraechTrefferWaehlen,
    taste: gespraechTrefferTaste,
    schliessen: gespraechTrefferSchliessen,
  },
  gespraechSucheStand: () => ({
    offen: gespraechSucheOffen.value,
    begriff: gespraechSucheBegriff.value,
    treffer: gespraechTreffer.value,
    mehr: gespraechSucheMehr.value,
    fehler: gespraechSucheFehler.value,
    aktiv: gespraechTrefferAktiv.value,
  }),
  // CHAT-6-UI: der Meldeweg der Seite (gemountet prüfbar: Auswahl → POST).
  meldenOeffnen,
  meldungSenden,
  meldeDialog,
  meldeLaeuft,
  meldeFehler,
  meldeEingegangen,
})

// ── Start und Wechsel ──────────────────────────────────────────────────────

onMounted(async () => {
  aktivSeite = true
  window.addEventListener('hashchange', hashGeaendert)
  // Review R1, MUSS 2: „Zurück“ und „Vorwärts“ laufen über `popstate` (der
  // Browser feuert es auch für den Zurück-Weg über einen `pushState`-Eintrag;
  // `hashchange` kommt bei `pushState`/`replaceState` gar nicht).
  window.addEventListener('popstate', verlaufGeaendert)
  if (!modulAn.value) return
  // MUSS 4: Die Seite übernimmt den Zähler SOFORT — noch bevor sie ihre Liste
  // geholt hat. Sonst liefe in der Zwischenzeit der Takt der App-Wurzel (er
  // prüft `seiteOffen`, und das ist beim Aufbau noch nicht gesetzt) und
  // `meine_gespraeche` ginge zweimal raus. `null` = „noch keine Zahl“; der
  // App-Zähler übernimmt sie unverändert und fragt nicht selbst nach.
  mitteilungSenden(null)
  mitteilungSeite(true)
  // Erst laden und öffnen; DANN den Takt starten — steht die Seite bis dahin
  // nicht mehr (`onUnmounted` lief bereits), startet er nicht mehr (MUSS 3).
  // CHAT-7b-UI-b: die EIGENE Sperrliste — EIN Aufruf beim Öffnen (nicht je
  // Gespräch). Sie entscheidet, ob der Aufheben-Weg im Hinweis steht und ob
  // die Aktion „Nicht mehr anschreiben lassen“ noch angeboten wird.
  await Promise.all([laden(), sperrListeLaden()])
  if (!aktivSeite) return
  // CHAT-3c-2 (SOLL 2): Die Adresse bleibt, WIE SIE IST. Kam die Seite über
  // eine Suchadresse (`#/nachrichten/suche?q=bert&offen=CHAT-1` — neu geladen,
  // geteilter Link, Zurück vom Profil), stehen Suche UND Gespräch schon:
  // `suchBegriff`/`offenAusAdresse` kommen aus der Adresse, die Treffer sucht
  // die Komponente beim Aufbau, `oeffnen()` holt den Verlauf von
  // `offeneKennung`. Nichts wird ersetzt, nichts geschlossen (Review R1:
  // vorher wurde hier die Adresse auf das Gespräch gestellt und die Suche
  // fiel weg).
  await oeffnen()
  if (!aktivSeite) return
  takt.starten()
})

onUnmounted(() => {
  aktivSeite = false
  // CHAT-9b-2: ein offener Entprell-Termin der Auswahl gehört niemandem mehr.
  erwaehnungEntprellt.beenden()
  takt.anhalten()
  // CHAT-11b: Sprung-Markierung und Gesprächssuche ebenso.
  if (markierTimer) { clearTimeout(markierTimer); markierTimer = null }
  sprungAbbau()
  gespraechSuchBremse.beenden()
  window.removeEventListener('hashchange', hashGeaendert)
  window.removeEventListener('popstate', verlaufGeaendert)
  // MUSS 4: Zähler wieder an die App-Wurzel zurückgeben (sie übernimmt den
  // letzten bekannten Stand und fragt im eigenen, langen Takt weiter).
  mitteilungSeite(false)
})

// Gesprächswechsel INNERHALB der Seite (Adresswechsel ohne neuen Aufbau).
// Die rechte Spalte folgt `offeneKennung`: beginnt eine Suche, bleibt die
// Kennung dieselbe (das Gespräch aus `kennung` wurde zu `&offen=`) — der
// Verlauf steht, es wird NICHTS nachgeladen (Review R1, MUSS 1/SOLL 6).
// Endet sie, tritt das Gespräch aus der Adresse an dieselbe Stelle: ebenfalls
// dieselbe Kennung, kein zweites Laden, kein zweiter Lesestand (SOLL 3).
// Nur ein echter Wechsel — anderes Gespräch oder zurück zur Liste — öffnet
// neu, und auch das nur, wenn der Verlauf hier nicht schon steht (`oeffnen`).
watch(() => offeneKennung.value, async (neu, alt) => {
  if (!modulAn.value || !aktivSeite) return
  if (neu === alt) return
  // Review R1, Punkt 6: der ruhige Hinweis „… gesperrt“ gehört zum Gespräch,
  // in dem er entstand — beim Wechsel (anderes Gespräch oder zurück zur
  // Liste) verstummt er, statt beim nächsten 1:1 als Satz über die FALSCHE
  // Person zu stehen.
  sperrErfolgText.value = ''
  if (neu) {
    fehlschlaege = 0
    await oeffnen()
    return
  }
  fehlschlaege = 0
  zuruecksetzen()
})

// CHAT-3c (Review R1, SOLL e): Kommt die Suche über die ADRESSE zurück (Zurück
// vom Profil — dieselbe Seite bleibt gemountet, die Komponente auch), hat
// `suchBegriff` den Begriff erneut, während die Komponente ihn in der
// Zwischenzeit nicht kannte. Sie muss ihn erfahren — ihre Treffer hängen an
// DIESEM Wert (ihr eigenes Feld blieb unberührt, darum fragt sie nicht neu).
//
// CHAT-3c-2: Der Vergleich „schon gemeldet“ läuft gegen das, was die
// KOMPONENTE zuletzt von hier bekam (`gemeldeterBegriff`) — vorher stand hier
// ein `zuletztGetippt`, das nie geschrieben wurde (toter Code), der Watcher
// war also wirkungslos.
const sucheEl = ref(null)
/** Der Begriff, den die Komponente zuletzt von hier bekommen hat. */
let gemeldeterBegriff = ''
watch(suchBegriff, (neu) => {
  if (!sucheOffen.value || !neu) return
  if (neu === gemeldeterBegriff) return
  // Nur ein Zurück/Vorwärts (oder ein neuer Aufbau) stellt den Begriff wieder
  // her — kein laufendes Tippen: `begriffGeaendert` hat ihn schon gemeldet.
  const baustein = sucheEl.value
  if (!baustein || typeof baustein.begriffSetzen !== 'function') return
  gemeldeterBegriff = neu
  baustein.begriffSetzen(neu)
})

</script>

<style scoped>
/* Der Bereich nimmt die verfügbare Höhe: Liste links (bis 340 px), Verlauf
   rechts. Am Handy EINE Spalte — die Seite zeigt dann entweder Liste oder
   Verlauf (Entwurf B-handy: eine Ebene, kein Seitenbaum).

   CHAT-3a-4 (MUSS 1): Die Höhe kommt NICHT mehr aus einem geschätzten Abzug
   („Viewport minus Kopf minus Abstände“) — der geschätzte Wert war zu groß,
   das Eingabefeld fiel unter den Rand. Die Seite ist eine Flex-Spalte über
   die VOLLE Höhe ihres Kastens (`.dk-content`); der Bereich füllt den Rest
   (`flex: 1`, `min-height: 0`), der Verlauf scrollt INNEN. Krumen und
   Seitenkopf wirken damit nur noch über ihre echte Höhe. */
.dk-chat {
  display: flex;
  flex-direction: column;
  /* `.dk-screen` trägt oben/unten 36/80 px Polster — hier bleiben die Seiten
     (40 px) stehen, die Höhe trägt der Flex-Fluss. */
  padding-bottom: var(--sp-5);
  min-height: 0;
}
.dk-chat :deep(.dk-ui-pageheader) { flex: none; }
.dk-chat-bereich {
  flex: 1 1 auto;
  display: grid;
  grid-template-columns: minmax(260px, 340px) minmax(0, 1fr);
  min-height: 0;
  /* LEISTE-1: KEIN äußerer Kartenrahmen mehr (Entwurf Variante A, DMB-4971:
     „Vollbild ohne Dopplungen“). Liste und Verlauf nehmen die Fläche bis an
     die Ränder; die Trennung leistet die Linie zwischen den Spalten. */
  background: var(--surface);
  overflow: hidden;
}
.dk-chat-liste-spalte {
  display: flex;
  flex-direction: column;
  min-height: 0;
  border-right: var(--rahmen-breite) solid var(--divider);
  overflow: hidden;
}
.dk-chat-verlauf-spalte {
  display: flex;
  flex-direction: column;
  min-height: 0;
  min-width: 0;
  background: var(--bg-subtle);
}
.dk-chat-nichts {
  display: grid;
  place-items: center;
  height: 100%;
  padding: var(--sp-5);
}
.dk-chat-verlauf {
  display: flex;
  flex-direction: column;
  min-height: 0;
  height: 100%;
}
.dk-chat-verlauf-kopf {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  padding: var(--sp-3) var(--sp-4);
  border-bottom: var(--rahmen-breite) solid var(--divider);
  background: var(--surface);
  flex: none;
}
.dk-chat-zurueck {
  display: none;
  align-items: center;
  justify-content: center;
  min-width: var(--control-h);
  min-height: var(--control-h);
  border-radius: var(--radius);
  color: var(--text);
  text-decoration: none;
  font-size: var(--fs-20);
}
.dk-chat-zurueck:focus-visible { outline: var(--rahmen-breite) solid var(--focus-ring); outline-offset: var(--rahmen-breite); }
.dk-chat-verlauf-titel { min-width: 0; flex: 1 1 auto; }
.dk-chat-verlauf-titel h2 {
  margin: 0;
  font-size: var(--fs-16);
  font-weight: var(--fw-fett);
  color: var(--text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.dk-chat-verlauf-unter {
  margin: 0;
  font-size: var(--fs-12);
  color: var(--muted);
}
.dk-chat-stumm-hinweis { color: var(--subtle); }
/* CHAT-3a-4 (SOLL 3): Stumm als Symbolknopf im Verlaufskopf — Trefferfläche
   aus `--control-h` (40 px mit Maus, 44 px am Finger), Beschriftung nur für
   die Vorlesehilfe (`aria-label`/`title`). */
.dk-chat-stumm-knopf {
  flex: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: var(--control-h);
  height: var(--control-h);
  margin-left: auto;
  border: var(--rahmen-breite) solid transparent;
  border-radius: var(--radius);
  background: transparent;
  color: var(--muted);
  font-size: var(--fs-16);
  line-height: 1;
  cursor: pointer;
}
.dk-chat-stumm-knopf:hover { background: var(--surface-hover); color: var(--text); }
.dk-chat-stumm-knopf:focus-visible { outline: var(--rahmen-breite) solid var(--focus-ring); outline-offset: var(--rahmen-breite); }

.dk-chat-nachrichten {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
  padding: var(--sp-4);
  list-style: none;
}
.dk-chat-nachrichten:focus-visible { outline: var(--rahmen-breite) solid var(--focus-ring); outline-offset: calc(var(--rahmen-breite) * -2); }
/* Die Liste der Nachrichten INNERHALB der Log-Region (role="log" trägt keine
   <li>) — kein eigenes Layout, die Blasen tragen es. */
.dk-chat-verlaufsliste {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
}
/* Kleiner Hinweis nach einem misslungenen Poll — ruhig, kein Alarm. */
.dk-chat-hinweis {
  margin: 0;
  padding: var(--sp-1) var(--sp-4);
  color: var(--subtle);
  font-size: var(--fs-12);
}
/* CHAT-11b (R1/6): Der Hinweis auf eine verlorene Nachricht steht als ruhige
   Fläche — er soll gelesen werden, ohne wie ein Fehler auszusehen. */
.dk-chat-sprungweg--liste {
  margin: var(--sp-2) var(--sp-3);
  padding: var(--sp-2) var(--sp-3);
  border-radius: var(--radius);
  background: var(--surface-2);
  color: var(--muted);
}
/* CHAT-7b-UI (Karte Punkt 5): der Eintritts-Hinweis steht RUHIG über dem
   Verlauf — kleine Fläche, kein Alarm, damit er sich von den Nachrichten
   abhebt, ohne sie zu verdrängen. */
.dk-chat-eintritt {
  padding: var(--sp-2) var(--sp-3);
  border-radius: var(--radius);
  background: var(--surface-2);
  color: var(--muted);
}
/* CHAT-7b-UI (Karte Punkt 3): die Aktionen im Rundenkopf und die
   aufklappbare Teilnehmerliste. Nur Tokens. */
.dk-chat-kopf-knopf { flex: none; }
.dk-runde-teilnehmer-knopf { align-self: flex-start; }
.dk-runde-teilnehmer {
  list-style: none;
  margin: var(--sp-1) 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--sp-1);
  max-height: calc(var(--sp-8) * 2);
  overflow-y: auto;
}
.dk-runde-teilnehmer-link {
  font-size: var(--fs-12);
  color: var(--text);
  text-decoration: none;
}
.dk-runde-teilnehmer-link:hover { text-decoration: underline; }
.dk-runde-teilnehmer-link:focus-visible { outline: var(--rahmen-breite) solid var(--focus-ring); outline-offset: var(--rahmen-breite); }
/* CHAT-7b-UI: der Dialog „Person vorschlagen“ — Rumpf und Fehlertext. */
.dk-runde-vorschlag { display: flex; flex-direction: column; gap: var(--sp-2); }
.dk-runde-hinweis { margin: 0; font-size: var(--fs-12); color: var(--muted); }
.dk-runde-fehler {
  margin: 0;
  padding: var(--sp-2) var(--sp-3);
  border-radius: var(--radius);
  background: var(--err-soft);
  color: var(--err);
  font-size: var(--fs-12);
}
.dk-chat-mehr {
  align-self: center;
  border: none;
  background: none;
  color: var(--muted);
  font-size: var(--fs-12);
  font-family: inherit;
  padding: var(--sp-1) var(--sp-2);
}
.dk-chat-mehr.is-knopf { text-decoration: underline; }
/* Die schmalen Textknöpfe sind DkButton (ghost/sm) — hier nur die Schrift. */
.dk-chat-textknopf { font-size: var(--fs-12); }
.dk-chat-tag {
  list-style: none;
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  color: var(--subtle);
  font-size: var(--fs-12);
  font-weight: var(--fw-mittel);
}
.dk-chat-tag::before,
.dk-chat-tag::after {
  content: '';
  height: 1px;
  background: var(--divider);
  flex: 1;
}
.dk-chat-fehler {
  margin: 0;
  padding: var(--sp-2) var(--sp-4);
  color: var(--err);
  font-size: var(--fs-12);
  background: var(--err-soft);
}

/* Eingabezeile unten (Entwurf B-desktop/B-handy). */
.dk-chat-eingabe {
  flex: none;
  padding: var(--sp-3) var(--sp-4);
  border-top: var(--rahmen-breite) solid var(--divider);
  background: var(--surface);
}
/* CHAT-7a (Karte Punkt 3): Senden gesperrt — ruhiger Hinweis statt Eingabe,
   der Verlauf darüber bleibt lesbar. Keine Alarmfarbe: es ist eine Auskunft,
   kein Fehler des Nutzers. */
.dk-chat-gesperrt { display: flex; flex-direction: column; gap: var(--sp-1); }
.dk-chat-gesperrt-titel { margin: 0; font-size: var(--fs-14); font-weight: var(--fw-mittel); color: var(--text); }
.dk-chat-gesperrt-text { margin: 0; font-size: var(--fs-12); color: var(--muted); }
.dk-chat-eingabe-zeile {
  display: flex;
  align-items: flex-end;
  gap: var(--sp-2);
  /* CHAT-9b: Bezug für die Vorschlagsliste der Erwähnungen — sie hängt ÜBER
     der Zeile und schiebt den Verlauf nicht. */
  position: relative;
}
/* CHAT-12b: Die Büroklammer ist so hoch wie das Eingabefeld (44 px) — am Handy
   mit dem Finger zu treffen, am Desktop unauffällig. */
.dk-chat-anhang-knopf { min-height: 44px; min-width: 44px; flex: none; }
.dk-chat-feld {
  flex: 1;
  min-height: var(--control-h);
  max-height: calc(var(--sp-8) * 2);
  resize: vertical;
  padding: var(--sp-2) var(--sp-3);
  border: var(--rahmen-breite) solid var(--rahmen-farbe);
  border-radius: var(--radius);
  background: var(--surface);
  color: var(--text);
  font-family: inherit;
  font-size: var(--fs-14);
  line-height: var(--lh-text);
}
.dk-chat-feld:focus-visible { outline: var(--rahmen-breite) solid var(--focus-ring); outline-offset: var(--rahmen-breite); }
.dk-chat-feld-gross { width: 100%; }
.dk-chat-antwortzeile {
  display: flex;
  align-items: baseline;
  gap: var(--sp-2);
  margin: 0 0 var(--sp-2);
  padding: var(--sp-1) var(--sp-2);
  border-left: var(--rahmen-breite) solid var(--accent);
  background: var(--surface-2);
  font-size: var(--fs-12);
  color: var(--muted);
}
.dk-chat-antwort-text { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.dk-chat-antwort-weg {
  margin-left: auto;
  border: none;
  background: none;
  color: var(--muted);
  font-size: var(--fs-12);
  font-family: inherit;
  cursor: pointer;
  text-decoration: underline;
}
.dk-chat-nur-vorlesen {
  position: absolute;
  width: var(--rahmen-breite);
  height: var(--rahmen-breite);
  margin: calc(var(--rahmen-breite) * -1);
  padding: 0;
  overflow: hidden;
  clip-path: inset(50%);
  white-space: nowrap;
  border: 0;
}

/* Handy: eine Spalte; die jeweils andere Ansicht ist ausgeblendet. Dieselbe
   Bedingung wie überall (`--layout-mobil`: grober Zeiger und schmal bzw. flaches
   Querformat) — „Chat ist am Handy nicht anders“, nur eine Ebene tiefer.

   CHAT-3c-2 (SOLL 4): Während der Suche zeigt die eine Spalte die SUCHFELD-
   und Trefferfläche — der Verlauf rechts ist dann ausgeblendet (`sucheOffen`
   an der Verlaufsspalte). „Zurück“ im Verlaufskopf führt erneut zur Suche
   (`zurueckZiel`), die Seitenleiste führt in die Liste. */
@media (max-width: 720px) {
  .dk-chat-bereich {
    grid-template-columns: 1fr;
    /* CHAT-3a-4 (MUSS 1): KEIN eigener Höhen-Abzug mehr — der Bereich füllt
       den Rest des Kastens (Basisregel), das Eingabefeld bleibt unten. Ein
       zweiter Schätzwert hier stand dem echten Kopf im Weg. */
  }
  .dk-chat-liste-spalte { border-right: none; }
  .dk-chat-bereich .nur-handy-aus { display: none; }
  .dk-chat-zurueck { display: inline-flex; }
}

/* ── LEISTE-1 · Kopf der Vollbild-Seite (nur Handy) ─────────────────────────
   ☰ (öffnet die Seitenleiste), Suchfeld, Glocke, Plus — in EINER Zeile
   (Entwurf „02 Nachrichten A Handy“). Am Desktop steht dort die Suche in der
   Liste, die Glocke in der Seitenleiste; die Zeile ist dort nicht im Weg. */
.dk-chat-leiste {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  padding: var(--sp-2) 0;
  flex: none;
}
.dk-chat-leiste-suche { flex: 1 1 auto; min-width: 0; }
/* Das Suchfeld dieser Zeile trägt keinen eigenen Außenabstand mehr — er
   gehört der Zeile (sonst stünde es doppelt eingerückt). */
.dk-chat-leiste .dk-chat-suchfeld { margin: 0; }
/* Läuft die Suche, wird die Zeile zum Kopf: das Trefferfeld scrollt INNEN,
   die Liste darunter verschwindet (sie ist am Handy ohnehin ausgeblendet) —
   die Zeile wächst also nicht über den Bildschirm hinaus. */
.dk-chat-leiste.is-suche { flex: 1 1 auto; align-items: flex-start; }
.dk-chat-leiste.is-suche .dk-chat-leiste-suche { display: flex; flex-direction: column; height: 100%; }

/* CHAT-3a-4 (SOLL 3/MUSS 1) · Handy-Lage (Klasse aus dem Handy-Composable,
   dieselbe Quelle wie das Gerüst `.dk-app--handy`, KEINE zweite
   Breakpoint-Regel):
   Der Chat nimmt den Kasten randlos ein, und die Eingabe sitzt direkt über
   der unteren Leiste. Den Streifen unter der Leiste (Safe-Area) trägt der
   INHALTSKASTEN schon selbst (`.dk-app--handy .dk-content` in index.css) —
   hier kommt KEIN zweiter Abstand dazu, sonst stand die Eingabe doppelt
   hoch. Die Seite selbst scrollt nicht mehr; nur der Verlauf innen.

   CHAT-3a-5 (B): Der Seitenrand (--sp-4) bleibt NUR an der LISTE stehen —
   randlos ist allein das offene Gespräch (`.is-gespraech`). Vorher nahm
   `padding: 0` der Liste ihren Rand mit. */
.dk-app--handy .dk-chat {
  padding: 0 var(--sp-4);
  max-width: none;
  /* BEF-KAL-UNTEN (Manuel 24.11., DMB-d43df8406c05): Fußabstand EINMAL, hier
     an der Seite. Bisher trug ihn der Inhaltskasten `.dk-content`
     (index.css) — der ist bei den Vollbild-Seiten aber die Flex-Säule der
     Seite, dort klaut ein `padding-bottom` dem Inhalt die Höhe (Kalender:
     unterste Zeile fiel unter die Leiste). Deshalb gilt der Kasten-Abstand
     für `dk-content--vollbild` nicht mehr; die Seite trägt ihn: untere Leiste
     (`--leiste-unten-h`) + Sicherheitszone + Luft. Die Eingabe behält ihre
     Luft INNEN (`.dk-chat-eingabe`, `--sp-3`) — das ist keine zweite Zählung
     der Leiste. */
  padding-bottom: calc(var(--leiste-unten-h) + env(safe-area-inset-bottom) + var(--sp-2));
  overflow: hidden;
}
/* Das OFFENE Gespräch nimmt die volle Breite (randlos); die Liste behält
   ihren Seitenrand. */
.dk-app--handy .dk-chat.is-gespraech {
  padding: 0;
}
.dk-app--handy .dk-chat .dk-chat-bereich {
  border-radius: 0;
  box-shadow: none;
}
.dk-app--handy .dk-chat .dk-chat-eingabe {
  /* BEF-KAL-UNTEN: Luft INNEN in der Eingabe — der Fußabstand der Seite
     (`--leiste-unten-h`) hält die Leiste frei. Zusammen bleibt es bei
     Leiste + Sicherheitszone + 12 px, jetzt aber ohne doppelte Zählung. */
  padding-bottom: var(--sp-3);
}

/* ── CHAT-11b · Suche im Gespräch und Sprung-Markierung ───────────────────── */

/* Die Suche im offenen Gespräch: Feld + Trefferliste UNTER dem Kopf, über dem
   Verlauf. Sie schiebt den Verlauf nicht weg, sondern bildet einen eigenen
   Block zwischen Kopf und Verlauf (der Verlauf behält `flex: 1`). */
.dk-chat-gespraechsuche {
  flex: none;
  display: flex;
  flex-direction: column;
  gap: var(--sp-1);
  padding: var(--sp-2) var(--sp-3) 0;
  border-bottom: var(--rahmen-breite) solid var(--rahmen-farbe-sanft);
  max-height: 45%;
  overflow-y: auto;
}
.dk-chat-gespraechsuche-feld {
  display: flex;
  align-items: center;
  gap: var(--sp-1);
  padding: 0 var(--sp-2);
  min-height: var(--control-h);
  border: var(--rahmen-breite) solid var(--rahmen-farbe);
  border-radius: var(--radius);
  background: var(--surface);
}
.dk-chat-gespraechsuche-input {
  flex: 1;
  min-width: 0;
  border: none;
  background: none;
  color: var(--text);
  font-family: inherit;
  font-size: var(--fs-14);
  padding: var(--sp-1) 0;
}
.dk-chat-gespraechsuche-input:focus { outline: none; }
.dk-chat-gespraechsuche-feld:focus-within {
  outline: var(--rahmen-breite) solid var(--focus-ring);
  outline-offset: var(--rahmen-breite);
}
.dk-chat-gespraechsuche-liste {
  list-style: none;
  margin: 0;
  padding: 0 0 var(--sp-2);
}
.dk-chat-gespraechsuche-zeile {
  display: flex;
  flex-direction: column;
  padding: var(--sp-1) var(--sp-2);
  border-left: var(--rahmen-breite) solid transparent;
  border-radius: var(--radius-sm);
  cursor: pointer;
  min-height: var(--control-h);
}
.dk-chat-gespraechsuche-zeile:hover { background: var(--surface-hover); }
.dk-chat-gespraechsuche-zeile.is-aktiv {
  background: var(--surface-2);
  border-left-color: var(--focus-ring);
}
.dk-chat-gespraechsuche-kopf {
  display: flex;
  align-items: baseline;
  gap: var(--sp-2);
}
.dk-chat-gespraechsuche-absender {
  flex: 1;
  min-width: 0;
  font-size: var(--fs-12);
  font-weight: var(--fw-mittel);
  color: var(--text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.dk-chat-gespraechsuche-zeit {
  flex: none;
  font-size: var(--fs-12);
  color: var(--subtle);
  font-variant-numeric: var(--fs-tabular);
}
.dk-chat-gespraechsuche-ausschnitt {
  font-size: var(--fs-12);
  color: var(--muted);
  overflow-wrap: anywhere;
}
/* Die Markierung: Gold-Fläche mit Text-Farbe — in beiden Themes lesbar (die
   Standard-Markierung des Browsers ist im Dunkelmodus grell). */
.dk-chat-gespraechsuche-ausschnitt mark {
  background: var(--accent-soft);
  color: var(--text);
  border-radius: var(--radius-sm);
  padding: 0 var(--sp-1);
}

/* Die gesprungene Nachricht: kurz ein Ring in der Fokusfarbe — dieselbe
   Gestalt wie ein Fokusring, damit sie ohne neue Farbe auffällt. */
.dk-chat-verlaufsliste :deep(.dk-chat-sprungziel) {
  border-radius: var(--radius);
  box-shadow: 0 0 0 var(--rahmen-breite) var(--focus-ring);
  transition: box-shadow 200ms ease-out;
}
</style>
