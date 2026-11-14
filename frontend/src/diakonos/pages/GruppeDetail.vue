<template>
    <div class="dk-screen dk-screen-enter">
        <!-- Seitenkopf -->
        <!-- UX1f (N4): „Wo bin ich“ — die Seite hatte weder Brotkrumen noch
             den Namen ihres Bereichs; jetzt führen die Krumen über „Gruppen“
             (Seitenname = Menüname) zur Gruppe. Der frühere Untertitel mit den
             Krumen ist damit doppelt und entfällt. -->
        <DkPageHeader
            :title="displayName"
            :sub="unterzeile"
            :krumen="[{ text: 'Gruppen', href: '#/gruppen' }, { text: displayName }]"
            :badges="[{ text: currentStatus || 'Unbekannt', variant: statusVariante }]"
        >
            <template #actions>
                <div v-if="verantwortliche.length > 0" class="grup-avatar">
                    <img v-if="sichereBildUrl(verantwortliche[0].foto)" :src="sichereBildUrl(verantwortliche[0].foto)" :alt="verantwortliche[0].name" />
                    <span v-else>{{ initials(verantwortliche[0].name) }}</span>
                </div>
            </template>
        </DkPageHeader>

        <!-- UI-R1: EINE Seite je Gruppe, zwei Reiter — „Übersicht“ (alles
             Bisherige) und „Einstellungen“ (Rollen). Der Reiter steht in der
             ADRESSE (#/gruppe/<id> und #/gruppe/<id>/einstellungen), damit
             Lesezeichen und der Zurück-Knopf wirken. „Einstellungen“ sieht
             nur, wer HV/MV/GL oder Administrator ist — entschieden wird das
             aus den Serverdaten (`get_gruppe_detail.rechte`), nicht aus einer
             lokalen Regel. Durchgesetzt wird ohnehin serverseitig. -->
        <DkReiter
            v-if="!erstLadend && !error && zeigeEinstellungenReiter"
            class="grup-reiter"
            :model-value="aktiverReiter"
            :options="reiterOptionen"
            aria-label="Bereiche dieser Gruppe"
        />

        <!-- OP-UI-19: Seitenkopf steht schon, der Inhalt ist ein Skelett statt
             eines nackten „Lade…“. Der Platzhalter erscheint erst, wenn das
             Laden merklich dauert (useLadeSkelett, UX2d2/UX2d3a).

             UI-R1b: Er steht NUR beim ERSTEN Laden. Jedes Nachladen nach einer
             Aktion (Aufgabe, Ankündigung, Mitglied, Details, Rollen) ist STILL
             — der Inhalt bleibt stehen, die Seite springt nicht nach oben und
             der Fokus bleibt, wo er war. -->
        <DkSkelett v-if="skelettSichtbar && !error" form="zeilen" :anzahl="5" text="Gruppe wird geladen …" />

        <!-- Fehler -->
        <DkHint v-if="!erstLadend && error" variant="err">{{ error }}</DkHint>

        <!-- Einstellungen: Teil 1 Rollen (UI-R1). Die Karte lädt ihre
             eigenen Daten; ob sie erscheint, entscheidet sie aus den
             Serverfeldern selbst (fail closed).

             EINE Bedingung für ALLE drei Zustände: solange das ERSTE Laden
             läuft ODER ein Fehler ansteht, gibt es hier KEINEN Inhalt — sonst
             stünde die Übersicht mit erfundenen Nullen unter dem Hinweis bzw.
             neben dem Skelett (UX2d2/OP-UI-19). Ein STILLES Nachladen
             (`nachladen`) blendet den Inhalt dagegen NICHT aus. -->
        <template v-if="!erstLadend && !error">
            <!-- Auf einer UNTERGRUPPEN-Seite gibt es nur die Gruppenleitung
                 dieser Untergruppe — kein HV/MV (die stehen in der
                 Obergruppe), siehe RollenEinstellungen. -->
            <template v-if="aktiverReiter === 'einstellungen'">
                <DkCard title="Rollen der Gruppe">
                    <GruppenEinstellungen
                        :gruppe="obergruppeId"
                        :untergruppe="untergruppeId"
                        :untergruppen="untergruppenFuerEinstellungen"
                        @geaendert="nachladen"
                    />
                </DkCard>
            </template>

            <template v-else>
            <!-- ab hier nur, wenn der Reiter NICHT „Einstellungen“ ist -->
            <!-- Zweispaltig -->
            <div class="grup-grid">
                <!-- LINKE SPALTE -->
                <div class="grup-spalte">
                    <!-- Details -->
                    <DkCard title="Details">
                        <template #actions>
                            <DkButton v-if="canManage && !editingDesc" variant="ghost" size="md" @click="startEditDesc" aria-label="Details bearbeiten">
                                <!-- UXD-R25: Stift statt „+“ (das Zeichen stand für Bearbeiten, sah aber wie Anlegen aus). -->
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 20h9"/><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg>
                            </DkButton>
                        </template>
                        <template v-if="!editingDesc">
                            <div v-for="z in detailZeilen" :key="z.label" class="grup-datenzeile">
                                <span class="grup-datenlabel">{{ z.label }}</span>
                                <span class="grup-datenwert">{{ z.wert }}</span>
                            </div>
                        </template>
                        <template v-else>
                            <div class="grup-formular">
                                <!-- OP-ADMIN-5: ohne Namensfeld ließ sich ein Tippfehler
                                     im Gruppennamen nie korrigieren. -->
                                <DkField label="Name">
                                    <input v-model="editName" class="dk-ui-eingabe" type="text" />
                                </DkField>
                                <DkField label="Beschreibung">
                                    <textarea v-model="editDesc" class="dk-ui-eingabe" rows="3" />
                                </DkField>
                                <DkField label="Treffpunkt">
                                    <input v-model="editTreffpunkt" class="dk-ui-eingabe" type="text" />
                                </DkField>
                                <DkField label="Treffzeit">
                                    <input v-model="editTreffzeit" class="dk-ui-eingabe" type="text" />
                                </DkField>
                                <!-- UX1f (S1): In der Bearbeitung ist „Speichern“ die
                                     eine Hauptaktion; „Abbrechen“ verwirft die Eingabe
                                     (Wortliste) und steht als secondary daneben.
                                     UX1h (S1): Im Bearbeiten-Zustand ist „Speichern“ der
                                     EINE gefüllte Knopf der Ansicht — die Kartenköpfe
                                     (Ankündigung/Aufgabe/Wiki) tragen nur ghost-Knöpfe. -->
                                <div class="grup-aktionen">
                                    <DkButton variant="primary" :loading="savingDesc" @click="saveDesc">Speichern</DkButton>
                                    <DkButton variant="secondary" @click="cancelEditDesc">Abbrechen</DkButton>
                                </div>
                            </div>
                        </template>
                    </DkCard>

                    <!-- P1-8 (OP-CHOR-3/OP-ADMIN-4): Verantwortliche pflegbar.
                         UI-R1 (Manuel 11.11.): Die frühere Karte
                         „Verantwortliche“ ist hier ENTFALLEN — die Rollen
                         (HV/MV/GL) stehen jetzt im Reiter „Einstellungen“.
                         Das alte Board schrieb über
                         `verantwortliche.set_verantwortliche` am EINEN
                         Rechtesystem vorbei und wird von der Gruppenseite
                         nicht mehr benutzt. -->

                    <!-- Termine -->
                    <DkCard title="Nächste Termine">
                        <!-- UI-R5 (Manuel 11.11.): „+ Termin“ wie bei den
                             Ankündigungen. Der Knopf erscheint nur, wenn der
                             SERVER für mindestens einen Kalender dieser Gruppe
                             Schreiben/Vorschlagen meldet (`get_accessible_calendars`
                             → `write`, zugeordnet über `gruppe`/`untergruppe`).
                             Die Oberfläche entscheidet hier nichts. -->
                        <template #actions>
                            <DkButton v-if="darfTermin" variant="ghost" size="md" @click="terminAnlegen" aria-label="Termin anlegen">
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
                            </DkButton>
                        </template>
                        <DkEmpty v-if="termine.length === 0" title="Keine bevorstehenden Termine" icon="📅" />
                        <div v-else class="grup-termine">
                            <div v-for="t in termine" :key="t.name" class="grup-termin">
                                <div class="grup-termin-datum">{{ formatDate(t.start || t.starts_on || t.datum) }}</div>
                                <div class="grup-termin-uhrzeit">{{ new Date(t.start || t.starts_on || t.datum).toLocaleTimeString('de-DE', {hour:'2-digit',minute:'2-digit'}) }}</div>
                                <div class="grup-termin-titel">{{ t.title || t.titel || t.subject || t.name }}</div>
                            </div>
                        </div>
                    </DkCard>

                    <!-- Ankündigungen -->
                    <DkCard title="Ankündigungen">
                        <template #actions>
                            <DkButton v-if="canManage" variant="ghost" size="md" @click="showAnkuendigungForm = !showAnkuendigungForm" aria-label="Ankündigung anlegen">
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
                            </DkButton>
                        </template>
                        <div v-if="showAnkuendigungForm" class="grup-formular grup-neu">
                            <input v-model="neueAnkuendigungTitel" type="text" placeholder="Titel" class="dk-ui-eingabe" />
                            <textarea v-model="neueAnkuendigungText" placeholder="Text (optional)" class="dk-ui-eingabe" rows="3" />
                            <div class="grup-aktionen">
                                <!-- UX1h (S1): je Karte genau eine gefüllte Aktion —
                                     „Veröffentlichen“ ist die Arbeit dieser Karte. -->
                                <DkButton variant="primary" :disabled="!neueAnkuendigungTitel.trim() || sendingAnkuendigung" :loading="sendingAnkuendigung" @click="createAnkuendigung">Veröffentlichen</DkButton>
                                <!-- UX1f: Hier wird eine Eingabe verworfen — das ist „Abbrechen“
                                     (Wortliste) und damit ein secondary der vollen Höhe. -->
                                <DkButton variant="secondary" @click="showAnkuendigungForm = false; neueAnkuendigungTitel = ''; neueAnkuendigungText = ''">Abbrechen</DkButton>
                            </div>
                        </div>
                        <DkEmpty v-if="ankuendigungen.length === 0" title="Keine Ankündigungen vorhanden" icon="📢" />
                        <ul v-else class="grup-liste">
                            <li v-for="a in ankuendigungen" :key="a.name" class="grup-eintrag">
                                <div class="grup-eintrag-kopf">
                                    <DkBadge v-if="a.pinned" variant="warn">Angepinnt</DkBadge>
                                    <span class="grup-eintrag-titel">{{ a.titel }}</span>
                                </div>
                                <p v-if="a.text" class="grup-eintrag-text">{{ truncate(a.text, 100) }}</p>
                            </li>
                        </ul>
                    </DkCard>
                </div>

                <!-- RECHTE SPALTE -->
                <div class="grup-spalte">
                    <!-- Aufgaben -->
                    <DkCard title="Aufgaben">
                        <template #actions>
                            <DkButton v-if="canManage" variant="ghost" size="md" @click="showAufgabeInput = !showAufgabeInput" aria-label="Aufgabe anlegen">
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
                            </DkButton>
                        </template>
                        <div v-if="showAufgabeInput" class="grup-formular grup-neu">
                            <DkField label="Aufgabe">
                                <input v-model="neueAufgabe" type="text" placeholder="Was ist zu tun?" class="dk-ui-eingabe" @keyup.enter="createAufgabe" />
                            </DkField>
                            <!-- UI-R9: Zuweisung schon beim Anlegen — die
                                 Auswahl sind die Mitglieder der (Unter-)Gruppe,
                                 die diese Seite ohnehin kennt. -->
                            <DkField label="Zuweisen an">
                                <DkSelect
                                    v-model="neueAufgabeZugewiesen"
                                    :options="zuweisungsOptionen(mitglieder)"
                                    aria-label="Aufgabe einer Person zuweisen"
                                />
                            </DkField>
                            <DkField label="Fällig am (optional)">
                                <input v-model="neueAufgabeFaellig" type="date" class="dk-ui-eingabe" />
                            </DkField>
                            <!-- UX1h (S1): je Karte genau eine gefüllte Aktion —
                                 „Übernehmen“ ist die Arbeit dieser Karte. -->
                            <div class="grup-aktionen">
                                <DkButton variant="primary" :disabled="!neueAufgabe.trim() || sendingAufgabe" :loading="sendingAufgabe" @click="createAufgabe">Übernehmen</DkButton>
                                <!-- UX1f (N8): „✕“ allein sagt nicht, was passiert (Eingabe
                                     verwerfen) — der sichtbare Name steht als „Abbrechen“ dran. -->
                                <DkButton variant="secondary" @click="aufgabeEingabeVerwerfen">Abbrechen</DkButton>
                            </div>
                        </div>
                        <DkEmpty v-if="aufgaben.length === 0" title="Noch keine Aufgaben" text="Hier sammelt die Gruppe, was zu tun ist. Wer verwalten darf, legt Aufgaben an und weist sie zu." icon="📋" />
                        <template v-else>
                            <p class="grup-zahl grup-aufgaben-zahl">{{ offenZahlText(aufgaben) }}</p>
                            <ul class="grup-liste">
                                <li v-for="a in aufgabenOffen" :key="a.name" class="grup-aufgabe" :data-aufgabe="a.name">
                                    <!-- Abhaken darf nur, wem die Aufgabe zugewiesen ist oder
                                         wer die Leitung hat — der Server sagt es je Zeile. -->
                                    <DkCheckbox
                                        :model-value="false"
                                        :disabled="!darfAbhaken(a) || aufgabeLaeuft === a.name"
                                        :aria-label="`„${a.titel}“ erledigt`"
                                        @update:model-value="toggleAufgabe(a)"
                                    />
                                    <div class="grup-aufgabe-haupt">
                                        <span class="grup-aufgabe-titel">{{ a.titel }}</span>
                                        <span class="grup-aufgabe-meta">
                                            <span v-if="zuweisungsText(a)" class="grup-aufgabe-zuweisung">{{ zuweisungsText(a) }}</span>
                                            <span v-if="faelligkeit(a).text" :class="['grup-aufgabe-frist', { 'is-ueberfaellig': faelligkeit(a).ueberfaellig }]">{{ faelligkeit(a).text }}</span>
                                        </span>
                                    </div>
                                    <DkAktionen
                                        v-if="darfBearbeiten(a)"
                                        :eintraege="aktionenFuerAufgabe(a)"
                                        :label="`… Menü für „${a.titel}“`"
                                    />
                                </li>
                            </ul>
                            <!-- Erledigte einklappbar: sie stehen unten, damit die offene
                                 Arbeit oben bleibt. -->
                            <div v-if="aufgabenErledigt.length" class="grup-aufgaben-erledigt">
                                <!-- UI-R9c (WCAG 2.5.3): der zugängliche Name ist
                                     der SICHTBARE Text. Das frühere aria-label
                                     („n erledigte Aufgaben ausblenden“) sagte
                                     etwas anderes als der Knopf anzeigte; jetzt
                                     schaltet auch der sichtbare Text um. -->
                                <DkButton
                                    ref="einklappKnopf"
                                    variant="ghost"
                                    size="md"
                                    class="grup-aufgaben-einklappen"
                                    :aria-expanded="zeigeErledigteAufgaben ? 'true' : 'false'"
                                    @click="zeigeErledigteAufgaben = !zeigeErledigteAufgaben"
                                >
                                    {{ erledigtKnopfText }}
                                </DkButton>
                                <ul v-if="zeigeErledigteAufgaben" class="grup-liste">
                                    <li v-for="a in aufgabenErledigt" :key="a.name" class="grup-aufgabe" :data-aufgabe="a.name">
                                        <DkCheckbox
                                            :model-value="true"
                                            :disabled="!darfAbhaken(a) || aufgabeLaeuft === a.name"
                                            :aria-label="`„${a.titel}“ wieder öffnen`"
                                            @update:model-value="toggleAufgabe(a)"
                                        />
                                        <div class="grup-aufgabe-haupt">
                                            <span class="grup-aufgabe-titel is-erledigt">{{ a.titel }}</span>
                                            <span class="grup-aufgabe-meta">
                                                <span v-if="zuweisungsText(a)" class="grup-aufgabe-zuweisung">{{ zuweisungsText(a) }}</span>
                                            </span>
                                        </div>
                                        <DkAktionen
                                            v-if="darfBearbeiten(a)"
                                            :eintraege="aktionenFuerAufgabe(a)"
                                            :label="`… Menü für „${a.titel}“`"
                                        />
                                    </li>
                                </ul>
                            </div>
                        </template>
                    </DkCard>

                    <!-- Wiki -->
                    <DkCard v-if="wikiArtikel.length > 0 || canManage" title="Wiki">
                        <template #actions>
                            <!-- R6: Der Sprung nimmt die GRUPPE mit, damit der
                                 Editor sie vorbelegt (`?gruppe=`). Ohne das
                                 wäre „auf der Gruppenseite vorbelegt“ nur ein
                                 leerer Satz gewesen. Bei einer Untergruppe
                                 stehen beide Kennungen in der Adresse. -->
                            <DkButton v-if="canManage" variant="ghost" size="md" aria-label="Wiki-Artikel anlegen" @click="navigate(wikiAnlegenZiel)">
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
                            </DkButton>
                        </template>
                        <DkEmpty v-if="wikiArtikel.length === 0" title="Noch keine Wiki-Artikel" icon="📖" />
                        <ul v-else class="grup-liste">
                            <li v-for="w in wikiArtikel" :key="w.name">
                                <a :href="`#/wiki/${w.name}`" class="grup-link">{{ w.titel || w.name }}</a>
                            </li>
                        </ul>
                    </DkCard>
                </div>
            </div>

            <!-- Untergruppen -->
            <DkCard v-if="untergruppen.length > 0" title="Untergruppen" class="grup-breit">
                <div class="grup-chips">
                    <a v-for="u in untergruppen" :key="u.name" :href="`#/gruppe/${u.name}`" class="grup-chip">
                        {{ u.untergruppenname || u.gruppenname || u.name }}
                    </a>
                </div>
            </DkCard>

            <!-- Mitglieder (Verwaltung) -->
            <DkCard v-if="canManage" title="Mitglieder" class="grup-breit">
                <template #actions>
                    <span class="grup-zahl">{{ zahlWort(mitglieder.length, 'Mitglied', 'Mitglieder') }}</span>
                </template>
                <div class="grup-zeile grup-zeile-abstand">
                    <MitgliedAuswahl
                        ref="mitgliedAuswahl"
                        aria-label="Mitglied zum Hinzufügen auswählen"
                        platzhalter="Mitglied suchen und auswählen…"
                        :lade-optionen="ladeMitgliederAuswahl"
                        @ausgewaehlt="mitgliedAusgewaehlt"
                    />
                </div>

                <DkEmpty v-if="mitglieder.length === 0" title="Keine Mitglieder vorhanden" icon="👤" />
                <DkTable v-else :spalten="mitgliederSpalten">
                    <!-- UX2e (Entwurf B1, N6): Der Zeilenknopf „Entfernen" ist ins
                         „⋯"-Menü gewandert; die Rolle lässt sich dort ebenfalls
                         ändern (dieselbe Serverfunktion). Rechtsklick auf die
                         Zeile öffnet dasselbe Menü. -->
                    <tr
                        v-for="m in mitglieder"
                        :key="m.name || m.mitglied"
                        @contextmenu.prevent="zeilenKontextmenue($event, m)"
                    >
                        <td class="grup-wert">
                            <a v-if="darfProfilLink(m) && m.mitglied" :href="`#/mitglied/${m.mitglied}`" class="grup-link">
                                {{ m.vollstaendiger_name || m.name || m.mitglied }}
                            </a>
                            <span v-else>{{ m.vollstaendiger_name || m.name || '–' }}</span>
                        </td>
                        <td>
                            <DkSelect v-model="m.rolle" :options="rollenOptionen" @update:model-value="updateRolle(m)" aria-label="Rolle" />
                        </td>
                        <td>
                            <DkBadge :variant="mitgliedStatusVariante(m.status)">{{ m.status || 'Unbekannt' }}</DkBadge>
                        </td>
                        <td class="grup-muted">{{ formatDate(m.beitrittsdatum) || '–' }}</td>
                        <td class="dk-zeilen-aktion">
                            <span class="grup-aktionen">
                                <DkAktionen
                                    :ref="el => setzeAktion(el, m)"
                                    :eintraege="aktionenFuerMitglied(m)"
                                    :label="`Aktionen für ${m.vollstaendiger_name || m.name || 'dieses Mitglied'}`"
                                />
                            </span>
                        </td>
                    </tr>
                </DkTable>
            </DkCard>

            <!-- Mitglieder (Übersicht) -->
            <DkCard v-if="!canManage && mitglieder.length > 0" title="Mitglieder" class="grup-breit">
                <!-- OP-HANDY-19: Vorher stand hier nur „N Mitglieder in dieser
                     Gruppe“ — die Namen waren unsichtbar und niemand
                     auffindbar. Die Liste nennt jetzt die Namen; welche Felder
                     sichtbar sind, entscheidet weiterhin allein der Server
                     (die Datensätze kommen maskiert an). -->
                <ul class="grup-namensliste">
                    <li v-for="m in mitglieder" :key="'nm' + (m.name || m.mitglied || m.vollstaendiger_name)" class="grup-namenszeile">
                        <!-- DSGVO-2d: eine gelöschte Person steht hier als
                             „Gelöschte Person“ ohne Profil-Link (der Server
                             liefert den Namen bereits so). -->
                        <a v-if="darfProfilLink(m) && m.mitglied" :href="`#/mitglied/${m.mitglied}`" class="grup-link">
                            {{ m.vollstaendiger_name || m.name || m.mitglied }}
                        </a>
                        <span v-else>{{ m.vollstaendiger_name || m.name || '—' }}</span>
                        <span v-if="m.rolle" class="grup-rolle">{{ m.rolle }}</span>
                    </li>
                </ul>
                <p class="grup-muted">{{ zahlWort(mitglieder.length, 'Mitglied', 'Mitglieder') }} in dieser Gruppe</p>
            </DkCard>
            </template>
        </template>

        <!-- UI-R5: EIN Termin-Formular für alle (dieselbe Komponente wie im
             Kalender). Die Kalenderauswahl ist auf die Kalender DIESER Seite
             begrenzt; die Rechte prüft weiterhin der Server.
             Review 5: Das Formular wird erst beim ersten Klick eingebunden
             (`v-if`) — vorher stand es dauerhaft im Baum, lud fünf Listen je
             Seitenaufruf (für JEDEN) und lief in den Wettlauf „kein
             Schreibrecht“, bevor der Knopf überhaupt sichtbar war. -->
        <KronosEventCreate
            v-if="terminFormEingebunden && darfTermin"
            v-model:show="showTerminForm"
            :initial-data="terminVorgabe"
            :kalender-vorgabe="terminKalender"
            @created="onTerminAngelegt"
        />
    </div>
</template>

<script>
import { ref, computed, nextTick, onMounted, watch } from 'vue'
import { useSession } from '../composables/useSession.js'
import { getRouteParam, currentHash, navigate } from '../router.js'
import { apiCall } from '../composables/useApi.js'
import { useLadeSkelett } from '../composables/useLadeSkelett.js'
// UX2g: EINE Quelle fuer angezeigte Fehlertexte statt Floskeln wie
// "Fehler beim Laden" / "Fehler beim Speichern".
import { aktionsfehler } from '../../shared/fehlertexte.js'
import { showToast } from '../composables/useToast.js'
// UX2c-Nacharbeit (Review 06.11.): Entfernen aus einer Gruppe ist NICHT
// vollständig umkehrbar (Beitrittsdatum/Rolle/Notiz gehen verloren) →
// Rückfrage statt „Rückgängig“.
import { bestaetigen } from '../composables/useBestaetigen.js'
import { useFormularSchutz } from '../composables/useFormularSchutz.js'
import { useVerlassenSchutz } from '../composables/useVerlassenSchutz.js'
// UI-R9: die Regeln der Aufgaben-Oberfläche (Kästchen/Menü nach Server-Flags,
// offen/erledigt, Zuweisungstext, Fälligkeit, Zuweisungs-Auswahl).
import {
    darfAbhaken, darfBearbeiten, teileNachErledigt, zuweisungsText, offenZahlText,
    faelligkeit, zuweisungsOptionen, anzeigeName,
} from '../composables/aufgaben.mjs'
// UI-R9: die eine Person für „Zuweisung ändern“ (modaler Personen-Dialog).
import { waehlePerson } from '../composables/usePersonenWahl.js'
import { darfProfilLink } from '../composables/geloeschte-person.mjs'
// UXD-R5: Foto-Adressen aus der Antwort gehen nur als relativer Pfad oder
// http(s) in ein `src` — `javascript:`/`data:` werden verworfen (dieselbe
// Schranke wie im Organigramm).
import { sichereBildUrl } from '../../shared/sichere-ausgabe.js'
import DkPageHeader from '../components/ui/DkPageHeader.vue'
import DkButton from '../components/ui/DkButton.vue'
import DkBadge from '../components/ui/DkBadge.vue'
import DkCard from '../components/ui/DkCard.vue'
import DkField from '../components/ui/DkField.vue'
import DkSelect from '../components/ui/DkSelect.vue'
import DkCheckbox from '../components/ui/DkCheckbox.vue'
import DkTable from '../components/ui/DkTable.vue'
// UX2e: EIN Aktionsmenü „⋯" für alle Listen (Entwurf B1).
import DkAktionen from '../components/ui/DkAktionen.vue'
import DkEmpty from '../components/ui/DkEmpty.vue'
import DkHint from '../components/ui/DkHint.vue'
import DkSkelett from '../components/ui/DkSkelett.vue'
import MitgliedAuswahl from '../components/MitgliedAuswahl.vue'
// OP-CHOR-12/K2: kein Klammerplural — „1 Mitglied“, „3 Mitglieder“.
import { zahlWort } from '../components/ui/begriffe.mjs'
// UI-R1: der Reiter „Einstellungen“ (Teil 1: Rollen). Die frühere Karte
// „Verantwortliche“ ist entfallen — die Rollen stehen jetzt dort.
import GruppenEinstellungen from '../components/gruppen/GruppenEinstellungen.vue'
import { darfEinstellungenSehen as darfEinstellungenSehenVon } from '../components/gruppen/gruppenEinstellungen.mjs'
// UI-R1: EINE Reiterzeile (Stil A4) — dieselbe wie unter „Personen“.
import DkReiter from '../components/ui/DkReiter.vue'
// UI-R5: dasselbe Termin-Formular wie im Kalender — plus die Regeln, welche
// Kalender zu dieser Seite gehören (reine Funktionen, getestet in
// tests/ui-r5-gruppen-termin.test.mjs).
import KronosEventCreate from '../components/kronos/KronosEventCreate.vue'
import {
    kalenderDerGruppe,
    vorbelegterKalender,
    formularZeitraum,
} from '../components/gruppen/gruppenTermin.mjs'

export default {
    name: 'GruppeDetail',
    components: {
        DkPageHeader, DkButton, DkBadge, DkCard, DkField, DkSelect,
        DkCheckbox, DkTable, DkEmpty, DkHint, MitgliedAuswahl,
        DkAktionen, GruppenEinstellungen, DkReiter, DkSkelett, KronosEventCreate,
    },
    setup() {
        const { isAdmin, user } = useSession()

        const gruppe = ref(null)
        const untergruppe = ref(null)
        const mitglieder = ref([])
        const verantwortliche = ref([])
        const untergruppen = ref([])
        const aufgaben = ref([])
        const ankuendigungen = ref([])
        const wikiArtikel = ref([])
        const termine = ref([])
        const isMember = ref(false)
        const loading = ref(true)
        // UX2d2/OP-UI-19: der Platzhalter erscheint erst, wenn das Laden
        // merklich dauert — und verdrängt dann den Inhalt vollständig.
        const { skelettSichtbar } = useLadeSkelett(loading)
        const error = ref(null)
        /** K5/B-2: die Auswahlliste, um sie nach dem Hinzufuegen neu zu laden. */
        const mitgliedAuswahl = ref(null)

        // Beschreibung Edit
        const editingDesc = ref(false)
        const editName = ref('')
        const editDesc = ref('')
        const editTreffpunkt = ref('')
        const editTreffzeit = ref('')
        const savingDesc = ref(false)

        // UXD-R29: Rückfrage beim Wegnavigieren, solange die Detail-Bearbeitung
        // offen ist und Eingaben offen stehen. `editingDesc` in `lesen()` sorgt
        // dafür, dass bei geschlossenem Formular nichts gefragt wird.
        const descSchutz = useFormularSchutz(
            () => (editingDesc.value
                ? { name: editName.value, desc: editDesc.value, treffpunkt: editTreffpunkt.value, treffzeit: editTreffzeit.value }
                : null),
            () => savingDesc.value,
        )
        useVerlassenSchutz(descSchutz)

        // Aufgaben
        const showAufgabeInput = ref(false)
        const neueAufgabe = ref('')
        const sendingAufgabe = ref(false)
        // UI-R9: Zuweisung und Fälligkeit schon beim Anlegen; „erledigt“ ist
        // eine eigene, einklappbare Gruppe; `aufgabeLaeuft` sperrt die Zeile
        // während des Abhakens (kein Doppelklick, kein zweiter Aufruf).
        const neueAufgabeZugewiesen = ref('')
        const neueAufgabeFaellig = ref('')
        const zeigeErledigteAufgaben = ref(false)
        const aufgabeLaeuft = ref('')

        // Ankündigungen
        const showAnkuendigungForm = ref(false)
        const neueAnkuendigungTitel = ref('')
        const neueAnkuendigungText = ref('')
        const sendingAnkuendigung = ref(false)

        // UI-R5: „+ Termin“ — Kalender dieser Seite (aus der Serverliste, mit
        // den Rechtefeldern) und der Zustand des Termin-Formulars.
        const meineKalender = ref([])
        const showTerminForm = ref(false)
        const terminVorgabe = ref({})
        // Review 5: Das Formular hängt per `v-if` an dieser Kennzahl — es wird
        // erst beim ersten Klick eingebunden (5 Anfragen je Seitenaufruf für
        // jeden waren zu viel, samt Wettlauf „kein Schreibrecht“).
        const terminFormEingebunden = ref(false)

        /**
         * Kennung dieser Seite aus dem ROUTER (nicht aus `window.location.hash`).
         *
         * Review UI-R5 (6): Die alte Fassung las `window.location.hash` in einem
         * `computed` — ein Hash ist keine reaktive Quelle. Der Wert blieb beim
         * ersten Rendern stehen, der Watcher unten lief ins Leere und die
         * Kalenderzuordnung rechnete weiter mit der alten Kennung. `getRouteParam`
         * liest `acceptedRoute` (ein `ref`) und wechselt Scope und Parameter
         * zusammen — damit ist die Kennung reaktiv.
         */
        const gruppeId = computed(() => String(getRouteParam('id', 'GruppeDetail') || ''))
        // UI-R9b: Ziele für den Fokus nach dem Abhaken (siehe `fokusNachAbhaken`).
        const einklappKnopf = ref(null)

        /** UI-R1: Serverrechte dieser (Unter-)Gruppe — nur zum Ausblenden. */
        const rechte = ref({ verwalten: false, rollen: false })
        /**
         * UI-R1b: Ist der Inhalt schon EINMAL da? Nur das erste Laden zeigt
         * das Skelett und nimmt den Inhalt weg; jedes Nachladen danach ist
         * still (`nachladen`).
         */
        const geladen = ref(false)

        /**
         * UI-R1: Sichtbarkeit des Reiters. Das Template liest `rechte.verwalten`
         * bzw. `rechte.rollen` — die Feldnamen der Gruppen-Detail-Antwort —,
         * die Regel selbst steht EINMAL in `gruppenEinstellungen.mjs`.
         * Eine Hülle, weil `setup()`s Rückgabe eine gleichnamige importierte
         * Funktion überschreibt: Vorher stand hier die importierte Funktion
         * selbst, und `zeigeEinstellungenReiter` las sie als Wert → immer
         * `false`, der Reiter erschien nie.
         */
        const rechteFuerReiter = () => ({
            darf_verwalten: Boolean(rechte.value?.verwalten),
            darf_hv_mv_ernennen: Boolean(rechte.value?.rollen),
        })
        const zeigeEinstellungenReiter = computed(() => darfEinstellungenSehenVon(rechteFuerReiter()))
        /** UI-R1b: „Es wird gerade geladen, aber es gibt noch keinen Inhalt“. */
        const erstLadend = computed(() => Boolean(loading.value) && !geladen.value)

        /** UI-R1: der Reiter steht in der Adresse (`…/einstellungen`). */
        const aktiverReiter = computed(() => {
            const hash = String(currentHash.value || '')
            return /\/einstellungen\/?$/.test(hash) ? 'einstellungen' : 'uebersicht'
        })

        /**
         * UI-R1: Kennung der Gruppe, unter der die Rollen liegen.
         * `get_gruppenrollen`/`ernenne_mv`/`uebertrage_hv` arbeiten mit der
         * HAUPTgruppe; auf einer Untergruppen-Seite ist das die Obergruppe
         * (`untergruppe.gruppe` aus `get_gruppe_detail`).
         */
        const obergruppeId = computed(() => {
            if (untergruppe.value) return String(untergruppe.value.gruppe || '')
            return gruppeId.value
        })
        /** UI-R1: Kennung DIESER Untergruppe (nur dort gesetzt) — für GL. */
        const untergruppeId = computed(() => (untergruppe.value ? String(untergruppe.value.name || gruppeId.value) : ''))

        const reiterOptionen = computed(() => {
            const id = gruppeId.value
            const optionen = [{ value: 'uebersicht', label: 'Übersicht', href: `#/gruppe/${id}` }]
            if (darfEinstellungenSehenVon(rechteFuerReiter())) {
                optionen.push({ value: 'einstellungen', label: 'Einstellungen', href: `#/gruppe/${id}/einstellungen` })
            }
            return optionen
        })

        /**
         * UI-R1: Wer den Reiter nicht sehen darf, landet über eine
         * gespeicherte Adresse `…/einstellungen` nicht auf einer leeren Karte —
         * die Adresse wird auf die Übersicht zurückgesetzt.
         *
         * UI-R1b: ERSETZEN statt `navigate()` — der Rückfall darf keinen
         * eigenen Verlaufseintrag anlegen, sonst führt der Zurück-Knopf wieder
         * auf die gerade verworfene Adresse (eigene Zurück-Falle).
         *
         * UI-R1c (Review): `history.replaceState` allein GENÜGT NICHT. Es
         * schreibt nur die Adresszeile um und löst KEIN `hashchange` aus — der
         * Router behält dann `…#/gruppe/Chor/einstellungen`, `aktiverReiter`
         * bleibt „einstellungen“, und gezeichnet wird die (hier leere) Karte
         * „Rollen der Gruppe“ statt der Übersicht. `location.replace` ändert
         * den Hash ebenfalls ohne neuen Verlaufseintrag, FEUERT aber
         * `hashchange` — der Router zieht nach. Dasselbe Muster wie die
         * Weiterleitungen im Router (router.js, `window.location.replace(…)`).
         */
        watch([() => erstLadend.value, () => error.value, zeigeEinstellungenReiter, aktiverReiter],
            ([laedt, fehlerWert, sehen, reiter]) => {
                if (laedt || fehlerWert || sehen || reiter !== 'einstellungen') return
                window.location.replace(`#/gruppe/${gruppeId.value}`)
            })

        /** Untergruppen der Gruppe als { name, anzeigename } für die Rollen. */
        const untergruppenFuerEinstellungen = computed(() => (Array.isArray(untergruppen.value)
            ? untergruppen.value
            : [])
            .filter((u) => u && u.name)
            .map((u) => ({ name: String(u.name), anzeigename: u.untergruppenname || u.gruppenname || String(u.name) })))

        /**
         * R6 — Adresse „Wiki-Artikel anlegen“ MIT dieser Gruppe.
         *
         * Auf einer Gruppenseite weiß der Editor sonst nicht, für wen der
         * Artikel gedacht ist; die Karte verlangt ausdrücklich eine Vorauswahl.
         * Bei einer Untergruppe stehen beide Kennungen in der Adresse
         * (`?gruppe=…&untergruppe=…`), bei einer Hauptgruppe nur die Gruppe.
         */
        const wikiAnlegenZiel = computed(() => {
            const teile = []
            const ug = untergruppe.value
            const hauptgruppe = gruppe.value?.name || ug?.gruppe || ''
            if (hauptgruppe) teile.push(`gruppe=${encodeURIComponent(hauptgruppe)}`)
            if (ug?.name) teile.push(`untergruppe=${encodeURIComponent(ug.name)}`)
            return teile.length ? `#/wiki?${teile.join('&')}` : '#/wiki'
        })

        // Prüfe ob es eine Untergruppe ist (Untergruppe DocType hat kein gruppenname, sondern untergruppenname)
        const isUntergruppe = computed(() => !!untergruppe.value)

        // UI-R9b: der Name, NICHT die Kennung (der Link „Zur Gruppe“ zeigte
        // vorher „GRU-1“). Reihung siehe `anzeigeName` in aufgaben.mjs.
        const displayName = computed(() => anzeigeName(untergruppe.value, untergruppe.value?.name)
            || anzeigeName(gruppe.value, gruppe.value?.name) || 'Gruppe')

        const currentStatus = computed(() => {
            if (untergruppe.value) return untergruppe.value.status
            return gruppe.value?.status
        })

        const currentDesc = computed(() => {
            if (untergruppe.value) return untergruppe.value.beschreibung
            return gruppe.value?.beschreibung
        })

        const currentTreffpunkt = computed(() => {
            if (untergruppe.value) return untergruppe.value.treffpunkt
            return gruppe.value?.treffpunkt
        })

        const currentTreffzeit = computed(() => {
            if (untergruppe.value) return untergruppe.value.treffzeit
            return gruppe.value?.treffzeit
        })

        const breadcrumb = computed(() => {
            if (untergruppe.value && untergruppe.value.gruppe) {
                // UXD-R25: Obergruppe als Name (gruppe_name), nicht als rohe ID.
                return `${untergruppe.value.gruppe_name || untergruppe.value.gruppe} > ${displayName.value}`
            }
            if (gruppe.value?.dienstbereich) {
                // UXD-R25: Dienstbereichsname statt Zufalls-ID.
                return `${gruppe.value.dienstbereich_name || gruppe.value.dienstbereich} > ${displayName.value}`
            }
            return null
        })

        /** Untertitel: der Weg der Gruppe (wie die Krumen zuvor) — ohne den
         *  Gruppennamen, der schon als Titel steht (S3: keine Dopplung). */
        const unterzeile = computed(() => {
            if (untergruppe.value && (untergruppe.value.gruppe_name || untergruppe.value.gruppe)) {
                return `Untergruppe von ${untergruppe.value.gruppe_name || untergruppe.value.gruppe}`
            }
            if (gruppe.value?.dienstbereich) {
                return `Dienstbereich ${gruppe.value.dienstbereich_name || gruppe.value.dienstbereich}`
            }
            return ''
        })

        /**
         * UI-R10: „verwalten“ dieser Gruppe = Administrator ODER HV/MV der
         * Gruppe (Server: `_rechte.verwalten`). Die Mitgliederverwaltung
         * zählt hier NICHT mehr mit — seit R-11a vergibt sie keine Rollen in
         * Gruppen und legt keine an. `isAdmin` ist der Kern-Admin; die
         * Mitgliederliste der Verwaltung enthält `verantwortliche` bereits,
         * sodass HV/MV unverändert durchkommen.
         */
        const canManage = computed(() => {
            if (isAdmin.value) return true
            const email = user.value?.email
            if (!email) return false
            if (verantwortliche.value.some(v => v.email === email)) return true
            return false
        })

        // canView: User darf Gruppe-Dashboard sehen (Mitglied ODER canManage)
        const canView = computed(() => isMember.value || canManage.value)

        function initials(name) {
            if (!name) return '?'
            return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2)
        }

        function formatDate(val) {
            if (!val) return ''
            const d = new Date(val)
            if (isNaN(d.getTime())) return val
            return d.toLocaleDateString('de-DE')
        }

        function truncate(str, n) {
            if (!str) return ''
            // Strip HTML tags
            const plain = str.replace(/<[^>]+>/g, '')
            return plain.length > n ? plain.slice(0, n) + '...' : plain
        }

        /* Bausteine beschicken */
        const rollenOptionen = [
            { value: '', label: '–' },
            { value: 'Mitglied', label: 'Mitglied' },
            { value: 'Leiter', label: 'Leiter' },
            { value: 'Co-Leiter', label: 'Co-Leiter' },
            { value: 'Helfer', label: 'Helfer' },
            { value: 'Gast', label: 'Gast' },
        ]
        const mitgliederSpalten = [
            { key: 'name', label: 'Name' },
            { key: 'rolle', label: 'Rolle' },
            { key: 'status', label: 'Status' },
            { key: 'beitritt', label: 'Beitrittsdatum' },
            /* FIX-4: Aktionen-Spalte — `aktion: true` gibt dem `<th>` und der
               Zelle `.is-aktion` (Mindestbreite, Umbruch) und schaltet die
               Tabelle auf `table-layout: fixed`. */
            { key: 'aktionen', label: 'Aktionen', numeric: true, aktion: true },
        ]
        const statusVariante = computed(() => varianteFuer(currentStatus.value))
        function varianteFuer(status) {
            if (status === 'Aktiv') return 'ok'
            if (status === 'Inaktiv') return 'err'
            if (status === 'Pausiert') return 'warn'
            return 'neutral'
        }
        function mitgliedStatusVariante(status) { return varianteFuer(status) }

        /** Zeilen der Detailkarte. */
        const detailZeilen = computed(() => {
            const zeilen = [
                { label: 'Beschreibung', wert: currentDesc.value || '–' },
                { label: 'Treffpunkt', wert: currentTreffpunkt.value || '–' },
                { label: 'Treffzeit', wert: currentTreffzeit.value || '–' },
            ]
            // UXD-R25: Dienstbereich mit Namen statt roher ID.
            if (gruppe.value?.dienstbereich) {
                zeilen.push({
                    label: 'Dienstbereich',
                    wert: gruppe.value.dienstbereich_name || gruppe.value.dienstbereich,
                })
            }
            if (verantwortliche.value.length > 0) {
                zeilen.push({ label: 'Verantwortliche', wert: verantwortliche.value.map(v => v.name).join(', ') })
            }
            return zeilen
        })

        /**
         * Lädt die Gruppe.
         *
         * UI-R1b: `nachladen` ist der STILLE Weg — nach einer Aktion (Aufgabe,
         * Ankündigung, Mitglied, Details, Rollen) bleibt der Inhalt stehen.
         * Vorher setzte JEDES Laden `loading` und nahm damit den ganzen Inhalt
         * aus dem DOM: die Seite fiel zusammen, sprang nach oben und der Fokus
         * war weg. Skelett und Leerzustand hängen jetzt an `erstLadend`
         * (erster Aufbau) und `geladen`.
         */
        async function fetchGruppe({ nachladen = false } = {}) {
            const id = gruppeId.value
            if (!id) { loading.value = false; return }
            // UI-R1b: `loading` heißt „der Inhalt fehlt noch“ — es wird NUR
            // beim ersten Aufbau gesetzt. Ein stilles Nachladen lässt den
            // Inhalt samt geöffneter Bearbeitung stehen (kein Skelett, kein
            // leerer Frame, kein Fokusverlust).
            const sichtbarLaden = !nachladen && !geladen.value
            if (sichtbarLaden) loading.value = true
            error.value = null
            try {
                // UXD-R7: EINE Abfrage. Das Backend liefert bei einer
                // Untergruppen-ID deren Detail im selben Antwortformat — der
                // frühere Doppelversuch erzeugte bei jedem Untergruppen-Aufruf
                // einen 404 in der Konsole.
                const data = await apiCall('diakronos.diakonos.api.gruppen.get_gruppe_detail', { gruppe_id: id })
                if (data?.untergruppe) {
                    untergruppe.value = data.untergruppe
                    gruppe.value = null
                } else {
                    gruppe.value = data?.gruppe || null
                    untergruppe.value = null
                }
                mitglieder.value = data?.mitglieder || []
                verantwortliche.value = data?.verantwortliche || []
                untergruppen.value = data?.untergruppen || []
                aufgaben.value = data?.aufgaben || []
                ankuendigungen.value = data?.ankuendigungen || []
                wikiArtikel.value = data?.wiki_artikel || []
                isMember.value = data?.is_member || false
                // UI-R1: was der Server an dieser (Unter-)Gruppe erlaubt —
                // Grundlage für den Reiter „Einstellungen“. Keine lokale
                // Rechte-Regel: fehlt die Antwort, bleibt der Reiter zu.
                const r = data?.rechte || {}
                rechte.value = {
                    verwalten: Boolean(r.verwalten),
                    rollen: Boolean(r.rollen),
                }
                // Nächste Termine laden (UXD-R10: eigener Endpunkt; der alte
                // kalender.get_events-Aufruf scheiterte bei jedem Laden).
                try {
                    const kal = await apiCall('diakronos.diakonos.api.gruppen.get_gruppe_termine', {
                        gruppe_id: id, tage: 60,
                    })
                    termine.value = (kal?.termine || []).slice(0, 4)
                } catch (e) {
                    termine.value = [] // Termine sind Beiwerk, kein Seitenfehler
                }
                geladen.value = true
                // UI-R5: Kalender dieser Seite für „+ Termin“ (Beiwerk wie die
                // Termine selbst — scheitert es, gibt es keinen Knopf).
                await ladeMeineKalender()
            } catch (err) {
                // UI-R1b: Ein STILLES Nachladen darf den stehenden Inhalt
                // nicht wegnehmen — der Fehler geht als Meldung raus, die
                // Seite bleibt, wie sie war. Nur das ERSTE Laden füllt den
                // Fehlerhinweis der Seite.
                if (sichtbarLaden || !geladen.value) {
                    error.value = aktionsfehler('laden', err)
                } else {
                    showToast(aktionsfehler('laden', err), 'error')
                }
            } finally {
                loading.value = false
            }
        }

        /** UI-R1b: stilles Nachladen — der Inhalt bleibt stehen (siehe `fetchGruppe`). */
        function nachladen() {
            return fetchGruppe({ nachladen: true })
        }

        // --- Beschreibung Edit ---
        function startEditDesc() {
            editName.value = displayName.value || ''
            editDesc.value = currentDesc.value || ''
            editTreffpunkt.value = currentTreffpunkt.value || ''
            editTreffzeit.value = currentTreffzeit.value || ''
            editingDesc.value = true
            // UXD-R29: Grundstand erst nach dem Befüllen merken.
            descSchutz.merken()
        }

        function cancelEditDesc() {
            editingDesc.value = false
        }

        async function saveDesc() {
            const id = gruppeId.value
            // OP-ADMIN-5: leerer Name wird vorab abgefangen (der Server würde
            // sonst die Gruppe ohne Namen speichern bzw. mit Fehler abbrechen).
            if (!editName.value.trim()) {
                showToast('Bitte einen Namen angeben.', 'error')
                return
            }
            savingDesc.value = true
            try {
                const method = isUntergruppe.value
                    ? 'diakronos.diakonos.api.gruppen.update_untergruppe'
                    : 'diakronos.diakonos.api.gruppen.update_gruppe'
                // Feldname je Typ: Untergruppe nutzt `untergruppenname`, Gruppe
                // `gruppenname` — sonst meldet der Server „success“ ohne Wirkung.
                const params = isUntergruppe.value
                    ? { name: id, untergruppenname: editName.value.trim(), beschreibung: editDesc.value, treffpunkt: editTreffpunkt.value, treffzeit: editTreffzeit.value }
                    : { name: id, gruppenname: editName.value.trim(), beschreibung: editDesc.value, treffpunkt: editTreffpunkt.value, treffzeit: editTreffzeit.value }
                const res = await apiCall(method, params)
                if (res?.success) {
                    showToast('Gespeichert', 'success')
                    editingDesc.value = false
                    nachladen()
                } else {
                    showToast(aktionsfehler('speichern', res), 'error')
                }
            } catch (e) {
                showToast(aktionsfehler('speichern', e), 'error')
            } finally {
                savingDesc.value = false
            }
        }

        // --- Aufgaben ---
        /** Offene und erledigte Aufgaben getrennt (erledigte stehen eingeklappt unten). */
        const aufgabenOffen = computed(() => teileNachErledigt(aufgaben.value).offen)
        const aufgabenErledigt = computed(() => teileNachErledigt(aufgaben.value).erledigt)
        /** Beschriftung des Einklapp-Knopfs — auch sein zugänglicher Name
         *  (UI-R9c: kein abweichendes aria-label, WCAG 2.5.3). */
        const erledigtKnopfText = computed(() => {
            const n = aufgabenErledigt.value.length
            const was = n === 1 ? '1 erledigte Aufgabe' : `${n} erledigte Aufgaben`
            return `${was} ${zeigeErledigteAufgaben.value ? 'ausblenden' : 'anzeigen'}`
        })

        function aufgabeEingabeVerwerfen() {
            showAufgabeInput.value = false
            neueAufgabe.value = ''
            neueAufgabeZugewiesen.value = ''
            neueAufgabeFaellig.value = ''
        }

        async function createAufgabe() {
            // UXD-R11: Doppelklick erzeugte zwei Aufgaben. Sperre während des
            // Sendens; der Knopf ist zusätzlich :disabled/:loading.
            if (sendingAufgabe.value) return
            const titel = neueAufgabe.value.trim()
            if (!titel) return
            const id = gruppeId.value
            sendingAufgabe.value = true
            try {
                const params = isUntergruppe.value
                    ? { titel, untergruppe_id: id }
                    : { titel, gruppe_id: id }
                // Leer = niemanden zuweisen (der Server nimmt dafür `None`).
                if (neueAufgabeZugewiesen.value) params.zugewiesen_an = neueAufgabeZugewiesen.value
                if (neueAufgabeFaellig.value) params.faellig = neueAufgabeFaellig.value
                const res = await apiCall('diakronos.diakonos.api.gruppen.create_aufgabe', params)
                if (res?.success) {
                    aufgabeEingabeVerwerfen()
                    showToast('Aufgabe erstellt', 'success')
                    nachladen()
                } else {
                    showToast(aktionsfehler('anlegen', res), 'error')
                }
            } catch (e) {
                showToast(aktionsfehler('anlegen', e), 'error')
            } finally {
                sendingAufgabe.value = false
            }
        }

        async function toggleAufgabe(a) {
            if (!darfAbhaken(a) || aufgabeLaeuft.value) return
            aufgabeLaeuft.value = a.name
            const vorher = !!a.erledigt
            try {
                const res = await apiCall('diakronos.diakonos.api.gruppen.toggle_aufgabe', { aufgabe_id: a.name })
                if (res?.success) {
                    // UI-R9b: NICHT die ganze Seite neu laden (Skelett, Scroll
                    // und Fokus sprangen). Die Liste sortiert sich selbst
                    // (`aufgabenOffen`/`aufgabenErledigt` sind computed) —
                    // deshalb genügt das Umschalten der Zeile, danach wird
                    // still nachgeladen (ohne Ladeanzeige) und der Fokus auf
                    // die nächste Zeile bzw. den Einklapp-Knopf gesetzt.
                    a.erledigt = !!res.erledigt
                    await nachladenStill()
                    await nextTick()
                    fokusNachAbhaken(a)
                } else {
                    a.erledigt = vorher
                    showToast(aktionsfehler('speichern', res), 'error')
                }
            } catch (e) {
                a.erledigt = vorher
                showToast(aktionsfehler('speichern', e), 'error')
            } finally {
                aufgabeLaeuft.value = ''
            }
        }

        /**
         * Nachladen OHNE Ladeanzeige: `loading` bleibt false, das Skelett bleibt
         * aus. Die Termine werden nicht mitgeholt (sie ändern sich beim Abhaken
         * nicht). Scheitert es, bleibt die gezeigte Liste stehen.
         */
        async function nachladenStill() {
            const id = gruppeId.value
            if (!id) return
            try {
                const data = await apiCall('diakronos.diakonos.api.gruppen.get_gruppe_detail', { gruppe_id: id })
                aufgaben.value = data?.aufgaben || []
                mitglieder.value = data?.mitglieder || mitglieder.value
            } catch (e) {
                /* still: die Liste von eben bleibt stehen */
            }
        }

        /**
         * Fokus nach dem Abhaken: Die Zeile wandert aus der offenen Liste heraus.
         * Ziel ist die nächste offene Zeile (ihr Kästchen), sonst der
         * Einklapp-Knopf der erledigten Aufgaben — ein definierter Platz statt
         * des `<body>`.
         */
        function fokusNachAbhaken(a) {
            const weg = !!a?.erledigt
            const naechste = weg
                ? aufgabenOffen.value[0]
                : aufgabenErledigt.value[0]
            const zeilen = document.querySelectorAll('.grup-aufgabe[data-aufgabe]')
            let ziel = null
            if (naechste) {
                for (const zeile of zeilen) {
                    if (zeile.getAttribute('data-aufgabe') === naechste.name) {
                        ziel = zeile.querySelector('input[type="checkbox"]')
                        break
                    }
                }
            }
            if (!ziel) ziel = einklappKnopf.value?.$el || einklappKnopf.value?.el || null
            if (!ziel) ziel = zeilen.length ? zeilen[0].querySelector('input[type="checkbox"]') : null
            if (ziel && typeof ziel.focus === 'function') ziel.focus()
        }

        /* ── UI-R9 · Aktionsmenü der Aufgabenzeile ─────────────────────────
           Nur wer die Aufgabe verwalten darf (`darf_bearbeiten` vom Server),
           bekommt das „⋯“: Zuweisung ändern und Löschen. Das Löschen fragt im
           Dialog nach (kein `confirm()`) und sagt, dass es endgültig ist. */
        function aktionenFuerAufgabe(a) {
            // UI-R9c: KEIN „Zur Gruppe …“ mehr. `get_gruppe_detail` liefert je
            // Aufgabe kein `gruppe`/`untergruppe` (nur die Felder ohne
            // `mit_gruppe`), der Eintrag war hier immer abgeschaltet — und auf
            // dieser Seite zeigt er ohnehin auf die Seite selbst.
            return [
                {
                    key: 'zuweisen', label: 'Zuweisung ändern', icon: 'rolle',
                    aktion: () => zuweisungAendern(a),
                },
                {
                    key: 'loeschen', label: 'Löschen', icon: 'loeschen', gefahr: true,
                    aktion: () => deleteAufgabe(a),
                },
            ]
        }

        /**
         * Zuweisung ändern: der Personen-Dialog (`waehlePerson`) zeigt die
         * Mitglieder dieser (Unter-)Gruppe; die aktuelle Zuweisung ist
         * markiert, „Zuweisung aufheben“ setzt sie zurück. Der Server prüft
         * weiter (Leitung darf zuweisen, nur Personen der Gruppe).
         */
        async function zuweisungAendern(a) {
            const personen = zuweisungsOptionen(mitglieder.value)
            const ziel = await waehlePerson({
                titel: 'Zuweisung ändern',
                text: `Wer soll „${a.titel}“ übernehmen? Zugewiesen werden kann nur, wer zu dieser Gruppe gehört.`,
                optionen: personen.filter(p => p.value),
                aktuell: a.zugewiesen_an || '',
            })
            if (ziel === null) return // abgebrochen
            await setzeZuweisung(a, ziel || null)
        }

        async function setzeZuweisung(a, mitglied) {
            try {
                const res = await apiCall('diakronos.diakonos.api.gruppen.aufgabe_zuweisen', {
                    aufgabe_id: a.name,
                    mitglied: mitglied || null,
                })
                if (res?.success) {
                    showToast(mitglied ? 'Zugewiesen' : 'Zuweisung aufgehoben', 'success')
                    fetchGruppe()
                } else {
                    showToast(aktionsfehler('speichern', res), 'error')
                }
            } catch (e) {
                // 417 „Die Person gehört nicht zu dieser Gruppe.“ kommt als
                // verständlicher Satz an — aktionsfehler reicht ihn durch.
                showToast(aktionsfehler('speichern', e), 'error')
            }
        }

        async function deleteAufgabe(a) {
            const ok = await bestaetigen({
                titel: 'Aufgabe löschen?',
                text: `„${a.titel}“ wird endgültig entfernt. Das lässt sich nicht `
                    + 'rückgängig machen.',
                aktion: 'Löschen',
                gefahr: true,
            })
            if (!ok) return
            try {
                const res = await apiCall('diakronos.diakonos.api.gruppen.delete_aufgabe', { aufgabe_id: a.name })
                if (res?.success) {
                    showToast('Aufgabe gelöscht')
                    fetchGruppe()
                } else {
                    showToast(aktionsfehler('loeschen', res), 'error')
                }
            } catch (e) {
                showToast(aktionsfehler('loeschen', e), 'error')
            }
        }

        // --- Ankündigungen ---
        async function createAnkuendigung() {
            // UXD-R11: Doppelklick erzeugte zwei Ankündigungen.
            if (sendingAnkuendigung.value) return
            const titel = neueAnkuendigungTitel.value.trim()
            if (!titel) return
            const id = gruppeId.value
            sendingAnkuendigung.value = true
            try {
                const params = isUntergruppe.value
                    ? { titel, text: neueAnkuendigungText.value, untergruppe_id: id }
                    : { titel, text: neueAnkuendigungText.value, gruppe_id: id }
                const res = await apiCall('diakronos.diakonos.api.gruppen.create_ankuendigung', params)
                if (res?.success) {
                    neueAnkuendigungTitel.value = ''
                    neueAnkuendigungText.value = ''
                    showAnkuendigungForm.value = false
                    showToast('Ankündigung veröffentlicht', 'success')
                    nachladen()
                } else {
                    showToast(aktionsfehler('anlegen', res), 'error')
                }
            } catch (e) {
                showToast(aktionsfehler('anlegen', e), 'error')
            } finally {
                sendingAnkuendigung.value = false
            }
        }

        // --- Termine (UI-R5: „+ Termin“ auf dieser Gruppenseite) ---
        /**
         * Welche Kalender gehören zu DIESER Seite und dürfen beschrieben
         * werden? Zugeordnet über die Serverfelder `gruppe`/`untergruppe`;
         * bei einer Untergruppe zählt auch der Kalender der Hauptgruppe.
         * Ohne Schreibrecht ist der Eintrag nicht dabei — dann gibt es auch
         * keinen Knopf (die Oberfläche bietet nichts an, was der Server
         * verweigert).
         */
        const terminKalender = computed(() => kalenderDerGruppe(meineKalender.value, {
            gruppenId: gruppeId.value,
            hauptgruppe: untergruppe.value?.gruppe || null,
            istUntergruppe: isUntergruppe.value,
        }))

        /**
         * Darf die Seite „+ Termin“ anbieten? (mindestens ein Kalender)
         *
         * UI-R5 (Messlauf): Der Knopf erscheint erst, wenn die Kalenderliste
         * dieser Seite DA ist (`terminVorgabeBekannt`). Vorher öffnete ein
         * Klick das Formular mit einer leeren Vorgabe — und das hielt sie für
         * „keine Kalender dieser Seite“ (belegt: beim ersten Öffnen fehlte der
         * Untergruppen-Kalender). Die Liste kommt mit dem Seitenaufbau; der
         * Knopf folgt ihr, statt eine zweite Wartezeit zu erfinden.
         */
        const darfTermin = computed(() => terminVorgabeBekannt.value
            && terminKalender.value.length > 0)

        /**
         * UI-R5: Ist die Kalenderlage dieser Seite BEKANNT? Solange die
         * Serverliste fehlt (`meineKalender` leer), ist „kein Kalender“ nicht
         * dasselbe wie „keine Auswahl“: das Formular bekäme sonst eine LEERE
         * Vorgabe und hielte sie für „keine Kalender für diese Seite“ (im
         * Messlauf belegt: beim ersten Öffnen fehlte der Untergruppen-Kalender).
         * Deshalb hängen Knopf UND Formular daran.
         *
         * UI-R5b (Punkt 3): Die Weitergabe der Vorgabe braucht den Ternary
         * nicht mehr — `darfTermin` (das `v-if` des Formulars) enthält
         * `terminVorgabeBekannt` bereits, der Zweig `? terminKalender : null`
         * war immer wahr. Diese Prüfung bleibt: der KNOPF liest sie.
         */
        const terminVorgabeBekannt = computed(() => meineKalender.value.length > 0)

        /**
         * Kalenderliste des Aufrufers EINMAL holen — dieselbe Quelle, aus der
         * der Kalender seine Termine nimmt. Ein Fehler hier ist kein
         * Seitenfehler: dann gibt es schlicht keinen „+ Termin“-Knopf (der
         * Server bliebe ohnehin bei seiner Entscheidung).
         */
        async function ladeMeineKalender() {
            try {
                const liste = await apiCall('diakronos.kronos.api.permissions.get_accessible_calendars')
                meineKalender.value = Array.isArray(liste) ? liste : []
            } catch (e) {
                meineKalender.value = []
            }
        }

        /**
         * Knopf „+ Termin“: Formular öffnen.
         *
         * EIN Kalender → vorbelegt (die Person muss nichts wählen).
         * MEHRERE → kein Vorgabewert: das Formular lässt „Kalender“ leer und
         * verlangt die Auswahl („Diakronos fragt, für welchen“).
         */
        function terminAnlegen() {
            const vorbelegt = vorbelegterKalender(terminKalender.value)
            // UI-R5 (Review 2): Beginn UND Ende vollständig — sonst überspringt
            // `resetForm` den DEV-5-Vorschlag (es fasst nur ein Datum ohne
            // Uhrzeit an) und ohne Anfassen entstünde ein Termin OHNE Dauer.
            const zeitraum = formularZeitraum(new Date())
            terminVorgabe.value = {
                ...zeitraum,
                ...(vorbelegt ? { element_calendar: vorbelegt } : {}),
            }
            // Review 5: Das Formular wird erst jetzt eingebunden (`v-if`) — vorher
            // stand es dauerhaft im Baum und löste fünf Anfragen je Seitenaufruf
            // für JEDEN aus, samt Wettlauf „kein Schreibrecht“.
            terminFormEingebunden.value = true
            showTerminForm.value = true
        }

        /** Nach dem Speichern: Liste der nächsten Termine nachziehen. */
        function onTerminAngelegt() {
            showTerminForm.value = false
            fetchGruppe()
        }

        // --- Mitglieder ---
        /** BF1-E: Auswahlliste aller Mitglieder (Name, ggf. "bereits in der
         *  Gruppe"; KEINE E-Mail/Adressdaten — B-1).
         *
         *  B-2: Der Suchbegriff geht an den SERVER; die Liste ist nicht auf
         *  50 Eintraege abgeschnitten. Ohne Suche werden die ersten Treffer
         *  geliefert, beim Tippen filtert der Server umlaut- und
         *  gross-klein-unabhaengig (BF1-J). Die Berechtigung prueft der
         *  Server — der Gruppenverantwortliche darf sie sehen. Fehler werden
         *  im Feld angezeigt, nie verschluckt. */
        async function ladeMitgliederAuswahl(suche = '') {
            const id = gruppeId.value
            if (!id) return []
            const res = await apiCall('diakronos.diakonos.api.gruppen.get_gruppe_mitglieder_auswahl', {
                gruppe_id: id,
                is_untergruppe: isUntergruppe.value,
                suche: suche || '',
            })
            return Array.isArray(res) ? res : (res?.mitglieder || [])
        }

        /** Klick auf einen Eintrag der Auswahlliste: direkt hinzufuegen. */
        async function mitgliedAusgewaehlt(m) {
            if (!m?.mitglied) return
            const ok = await fuegeMitgliedHinzu(m.mitglied)
            // K5: nach dem Hinzufuegen die Auswahlliste neu laden — sonst
            // bleibt `in_gruppe` veraltet und der Eintrag sieht weiter
            // auswaehlbar aus.
            if (ok) mitgliedAuswahl.value?.neuLaden()
        }

        async function fuegeMitgliedHinzu(mitglied) {
            const id = gruppeId.value
            if (!id || !mitglied) return false
            try {
                const res = await apiCall('diakronos.diakonos.api.gruppen.add_mitglied_to_gruppe', {
                    gruppe_id: id,
                    mitglied_id: mitglied,
                    is_untergruppe: isUntergruppe.value,
                })
                if (res?.success) {
                    showToast('Mitglied hinzugefügt', 'success')
                    nachladen()
                    return true
                }
                showToast(aktionsfehler('anlegen', res), 'error')
                return false
            } catch (err) {
                showToast(aktionsfehler('anlegen', err), 'error')
                return false
            }
        }

        /* ── UX2e · Aktionsmenü der Mitgliederzeile (Entwurf B1, N6/K4) ───────
           Die Zeile hatte bisher EINEN Knopf („Entfernen"); jetzt trägt das
           „⋯"-Menü die Aktionen dieses Mitglieds IN dieser Gruppe:
             · Profil öffnen      (solange es ein Profil gibt)
             · Rolle ändern       (Untermenü-frei: die Rollen stehen als eigene
                                   Einträge — 5–8 Einträge, kein Erinnern)
             · Aus Gruppe entfernen (gefährlich, abgesetzt am Ende; derselbe
                                   Dialog wie bisher und dieselbe Serverfunktion)
           Rolle ändern gilt nur für Verwalter (dieselbe Bedingung wie das
           Rollen-Auswahlfeld daneben: `canManage`). */
        const aktionRefs = new Map()
        const mitgliedSchluessel = (m) => String(m.mitglied || m.name || '')
        function setzeAktion(el, m) {
            const schluessel = mitgliedSchluessel(m)
            if (!schluessel) return
            if (el) aktionRefs.set(schluessel, el)
            else aktionRefs.delete(schluessel)
        }

        function aktionenFuerMitglied(m) {
            const eintraege = []
            if (darfProfilLink(m) && m.mitglied) {
                eintraege.push({
                    key: 'profil', label: 'Profil öffnen', icon: 'ansehen',
                    aktion: () => navigate('#/mitglied/' + m.mitglied),
                })
            }
            if (canManage.value) {
                for (const r of rollenOptionen) {
                    if (r.value === (m.rolle || '')) continue
                    eintraege.push({
                        key: 'rolle-' + (r.value || 'ohne'),
                        label: r.value ? `Rolle „${r.label}"` : 'Rolle zurücksetzen',
                        icon: 'rolle',
                        aktion: () => rolleSetzen(m, r.value),
                    })
                }
            }
            eintraege.push({
                key: 'entfernen', label: 'Aus Gruppe entfernen', icon: 'entfernen',
                gefahr: true,
                aktion: () => removeMitglied(m),
            })
            return eintraege
        }

        /** Rolle setzen — derselbe Weg wie das Auswahlfeld (updateRolle). */
        async function rolleSetzen(m, wert) {
            m.rolle = wert
            await updateRolle(m)
        }

        /** Rechtsklick auf die Zeile öffnet dasselbe Menü. */
        function zeilenKontextmenue(ereignis, m) {
            aktionRefs.get(mitgliedSchluessel(m))
                ?.oeffnenFuerZeile(ereignis, ereignis?.currentTarget)
        }

        async function removeMitglied(m) {
            const id = gruppeId.value
            const mitglied_id = m.mitglied || m.name
            if (!id || !mitglied_id) return
            /* UX2c-Nacharbeit (Review 06.11.): Das Entfernen ist NICHT
               vollständig umkehrbar. `add_mitglied_to_gruppe` legt die
               Mitgliedschaft neu an und setzt dabei `beitrittsdatum` auf
               heute, `status` auf „Aktiv" und die Notiz auf leer — ein
               „Rückgängig" würde also einen anderen Zustand herstellen als
               vorher. Prinzip I2 der Karte („falls wiederherstellbar — sonst
               bleibt Rückfrage"): Rückfrage mit konkreter Folge, kein Undo. */
            const name = m.vollstaendiger_name || m.mitglied || m.name
            const ok = await bestaetigen({
                titel: 'Aus der Gruppe entfernen?',
                text: `${name} wird aus dieser Gruppe entfernt. Ein späteres `
                    + 'Aufnehmen beginnt neu (Beitrittsdatum heute, Rolle und Notiz '
                    + 'leer) — die bisherige Mitgliedschaft ist nicht wiederherstellbar.',
                aktion: 'Entfernen',
                gefahr: true,
            })
            if (!ok) return
            try {
                const res = await apiCall('diakronos.diakonos.api.gruppen.remove_mitglied_from_gruppe', {
                    gruppe_id: id,
                    mitglied_id: mitglied_id,
                    is_untergruppe: isUntergruppe.value,
                })
                if (res?.success) {
                    showToast(`${name} aus der Gruppe entfernt`)
                    nachladen()
                } else {
                    showToast(aktionsfehler('entfernen', res), 'error')
                }
            } catch (err) {
                showToast(aktionsfehler('entfernen', err), 'error')
            }
        }

        async function updateRolle(m) {
            const id = gruppeId.value
            const mitglied_id = m.mitglied || m.name
            if (!id || !mitglied_id) return
            try {
                const res = await apiCall('diakronos.diakonos.api.gruppen.update_mitglied_rolle', {
                    gruppe_id: id,
                    mitglied_id: mitglied_id,
                    rolle: m.rolle || '',
                    is_untergruppe: isUntergruppe.value,
                })
                if (res?.success) {
                    showToast('Rolle aktualisiert', 'success')
                } else {
                    showToast(aktionsfehler('speichern', res), 'error')
                }
            } catch (err) {
                showToast(aktionsfehler('speichern', err), 'error')
            }
        }

        onMounted(() => {
            fetchGruppe()
        })

        // UXD-R7: Wechselt nur der Routenparameter (z. B. Klick auf eine
        // Untergruppe), wird die Komponente mit :key in App.vue neu gebaut —
        // dieser Watcher deckt zusätzlich den Fall ab, dass dieselbe Instanz
        // denselben Hash behält (kein Remount möglich).
        watch(gruppeId, (neu, alt) => {
            if (neu && neu !== alt) fetchGruppe()
        })

        return {
            mitgliedAuswahl,
            skelettSichtbar,
            // DSGVO-2d: eine gelöschte Person hat kein Profil (kein Link).
            darfProfilLink,
            // UXD-R5: Bild-Adressen nur als relativer Pfad oder http(s).
            sichereBildUrl,
            // OP-CHOR-12/K2: Numerus-Helfer für „1 Mitglied“/„3 Mitglieder“.
            zahlWort,
            gruppe,
            untergruppe,
            mitglieder,
            verantwortliche,
            untergruppen,
            // UI-R1: Reiter „Einstellungen“ (Rollen).
            rechte,
            aktiverReiter,
            reiterOptionen,
            zeigeEinstellungenReiter,
            untergruppenFuerEinstellungen,
            // UI-R1: die Rollenliste hängt an der HAUPTgruppe (auf einer
            // Untergruppen-Seite die Obergruppe) und an der Untergruppe selbst.
            obergruppeId,
            untergruppeId,
            // UI-R1: das Template braucht die Gruppenkennung selbst
            // (`:gruppe="gruppeId"` am Bereich „Einstellungen“) — ohne die
            // Rückgabe war sie `undefined`, der Serveraufruf fiel aus.
            gruppeId,
            // UI-R1b: `@geaendert="nachladen"` des Bereichs „Einstellungen“ —
            // STILLES Nachladen, der Inhalt bleibt stehen.
            fetchGruppe,
            nachladen,
            // UI-R1b: erster Aufbau (`erstLadend`) — nur dann Skelett/Leerzustand.
            geladen,
            erstLadend,
            aufgaben,
            ankuendigungen,
            wikiArtikel,
            termine,
            isMember,
            loading,
            error,
            isAdmin,
            canManage,
            canView,
            displayName,
            currentStatus,
            currentDesc,
            currentTreffpunkt,
            currentTreffzeit,
            breadcrumb,
            unterzeile,
            editingDesc,
            editName,
            editDesc,
            editTreffpunkt,
            editTreffzeit,
            savingDesc,
            showAufgabeInput,
            neueAufgabe,
            sendingAufgabe,
            // UI-R9: Zuweisung/Fälligkeit beim Anlegen, getrennte Listen,
            // Menü nur bei Server-Erlaubnis, Kästchen nur bei `darf_abhaken`.
            neueAufgabeZugewiesen,
            neueAufgabeFaellig,
            zeigeErledigteAufgaben,
            aufgabeLaeuft,
            aufgabenOffen,
            aufgabenErledigt,
            erledigtKnopfText,
            einklappKnopf,
            darfAbhaken,
            darfBearbeiten,
            zuweisungsText,
            offenZahlText,
            faelligkeit,
            zuweisungsOptionen,
            aufgabeEingabeVerwerfen,
            aktionenFuerAufgabe,
            showAnkuendigungForm,
            neueAnkuendigungTitel,
            neueAnkuendigungText,
            sendingAnkuendigung,
            initials,
            formatDate,
            truncate,
            rollenOptionen,
            mitgliederSpalten,
            statusVariante,
            mitgliedStatusVariante,
            detailZeilen,
            startEditDesc,
            cancelEditDesc,
            saveDesc,
            createAufgabe,
            toggleAufgabe,
            createAnkuendigung,
            // UI-R5: „+ Termin“ — Kalender dieser Seite, Formular, Nachziehen.
            terminKalender,
            terminVorgabeBekannt,
            darfTermin,
            showTerminForm,
            terminVorgabe,
            terminFormEingebunden,
            terminAnlegen,
            onTerminAngelegt,
            ladeMitgliederAuswahl,
            mitgliedAusgewaehlt,
            removeMitglied,
            updateRolle,
            // UX2e: das Aktionsmenü der Mitgliederzeile.
            setzeAktion,
            aktionenFuerMitglied,
            zeilenKontextmenue,
            // B-3: `navigate('#/wiki')` steht im Template (Options-API ohne
            // <script setup>, keine globalProperties) — ohne diese Zeile war
            // der Wiki-Knopf `undefined` und der Klick warf einen TypeError.
            navigate,
            // R6: Sprungziel mit der Gruppe dieser Seite (Vorauswahl im Editor).
            wikiAnlegenZiel,
        }
    },
}
</script>

<style scoped>
/* FIX-5 (Befund DMB-096ae0364b59): „Gap zwischen den Kacheln nicht
   einheitlich“. Das Raster und die beiden Spalten hatten je eigenes gap,
   der Vollbreiten-Block darunter nur `margin-top`. Jetzt gilt EIN Abstand für
   alles: --grid-gap. Die Spalten sind zugleich `minmax(0, …)` — ohne die 0
   kann eine lange Zeile (z. B. eine lange Ankündigung) die Spalte breiter
   machen als ihr Anteil, und das Raster läuft am Handy seitlich über. */
.grup-grid {
    display: grid;
    grid-template-columns: minmax(0, 2fr) minmax(0, 1fr);
    gap: var(--grid-gap);
}
.grup-spalte { display: flex; flex-direction: column; gap: var(--grid-gap); min-width: 0; }
.grup-breit { margin-top: var(--grid-gap); }
@media (max-width: 720px) {
    .grup-grid { grid-template-columns: minmax(0, 1fr); }
}

/* FIX-5 (Befund DMB-096ae0364b59): „Kartenköpfe unterschiedlich hoch“.
   Innerhalb dieser Seite waren Kopfzeilen mit Aktionsknopf 4 px höher als
   solche ohne (Kopf mit Knopf 57 px, ohne 53 px): der Knopf (DkButton „sm“)
   ist höher als eine Zeile Titeltext. Der Ausgleich gilt NUR für die Karten
   dieser Seite — nicht in DkCard, damit nicht ~30 andere Stellen app-weit
   ihre Kopfhöhe ändern. Nebeneinander („Details“ mit Stift, „Nächste Termine“
   ohne) stehen dadurch beide auf derselben Höhe.
   :deep, weil der Kopf in DkCard (scoped) liegt. */
.dk-screen :deep(.dk-ui-card-kopf) {
    min-height: calc(var(--row-h) + 2 * var(--sp-2));
}

.grup-zustand { padding: var(--sp-6); text-align: center; color: var(--muted); }
/* UI-R1: die Reiterzeile sitzt zwischen Seitenkopf und Inhalt — gleicher
   Abstand wie die Karten zueinander (EIN Rastermaß, siehe .grup-grid). */
.grup-reiter { margin-bottom: var(--grid-gap); }
.grup-muted { color: var(--muted); font-size: var(--fs-sm); margin: 0; }
/* OP-HANDY-19: Namensliste der Gruppenmitglieder für Nicht-Verwalter. */
.grup-namensliste { list-style: none; margin: 0 0 var(--sp-3); padding: 0; display: flex; flex-direction: column; gap: 6px; }
.grup-namenszeile { display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap; font-size: var(--fs); }
.grup-rolle { color: var(--muted); font-size: var(--fs-sm); }
.grup-zahl { font-size: var(--fs-sm); color: var(--muted); }

.grup-datenzeile {
    display: flex;
    justify-content: space-between;
    gap: var(--sp-4);
    padding: var(--sp-2) 0;
    border-bottom: 1px solid var(--line);
}
.grup-datenzeile:last-child { border-bottom: none; }
.grup-datenlabel { font-weight: 500; color: var(--muted); }
/* FIX-5: `min-width: 0` — eine lange, unumbrüchliche Beschreibung (URL,
   @-Nennung) schob sonst die ganze Rasterspalte auseinander. */
.grup-datenwert { color: var(--text); text-align: right; min-width: 0; overflow-wrap: anywhere; }

.grup-formular { display: flex; flex-direction: column; gap: var(--sp-3); }
.grup-neu { margin-bottom: var(--sp-4); padding: var(--sp-3); border: 1px solid var(--line); border-radius: var(--radius); background: var(--surface-2); }
.grup-aktionen { display: flex; gap: var(--sp-2); flex-wrap: wrap; }
.grup-zeile { display: flex; gap: var(--sp-2); align-items: flex-end; }
.grup-zeile .dk-ui-eingabe { flex: 1; }
.grup-zeile-abstand { margin-bottom: var(--sp-4); }

.grup-termine { display: flex; gap: var(--sp-3); flex-wrap: wrap; }
/* FIX-5: `flex: 1` mit `min-width: 120px` ließ die Termin-Kacheln am Handy
   über die Kartenbreite hinauslaufen. `min-width: 0` erlaubt das Schrumpfen. */
.grup-termin {
    flex: 1 1 120px;
    min-width: 0;
    max-width: 160px;
    background: var(--surface-2);
    border: 1px solid var(--line);
    border-radius: var(--radius);
    padding: var(--sp-3);
    text-align: center;
}
.grup-termin-datum { font-size: var(--fs-h3); font-weight: 700; color: var(--text); }
.grup-termin-uhrzeit { font-size: var(--fs-xs); color: var(--muted); margin: 2px 0; }
.grup-termin-titel { font-size: var(--fs-sm); color: var(--text); }

.grup-avatar {
    width: 44px;
    height: 44px;
    border-radius: 50%;
    background: var(--dk-navy-400);
    color: var(--primary-ink);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: var(--fs-h3);
    font-weight: var(--fw-fett);
    flex-shrink: 0;
    overflow: hidden;
}
.grup-avatar img { width: 100%; height: 100%; object-fit: cover; }

.grup-liste { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: var(--sp-2); }
.grup-eintrag { padding: var(--sp-3); border: 1px solid var(--line); border-radius: var(--radius); background: var(--surface-2); }
.grup-eintrag-kopf { display: flex; align-items: center; gap: var(--sp-2); margin-bottom: var(--sp-1); }
.grup-eintrag-titel { font-weight: 500; color: var(--text); font-size: var(--fs-sm); }
.grup-eintrag-text { font-size: var(--fs-xs); color: var(--muted); margin: 0; }

.grup-aufgabe { display: flex; align-items: flex-start; gap: var(--sp-3); padding: var(--sp-2) 0; border-bottom: var(--rahmen-breite) solid var(--rahmen-farbe); }
.grup-aufgabe:last-child { border-bottom: none; }
.grup-aufgabe-titel { flex: 1; font-size: var(--fs-sm); color: var(--text); overflow-wrap: anywhere; }
.grup-aufgabe-titel.is-erledigt { text-decoration: line-through; color: var(--muted); }
/* UI-R9: Titel und Beiwerk (Zuweisung, Frist) stehen untereinander; das
   Kästchen bleibt oben, damit lange Titel die Zeile nicht sprengen. */
.grup-aufgabe-haupt { flex: 1; min-width: 0; display: flex; flex-direction: column; }
.grup-aufgabe-meta { display: flex; flex-wrap: wrap; gap: var(--sp-2); font-size: var(--fs-xs); color: var(--muted); }
.grup-aufgabe-zuweisung { font-weight: var(--fw-fett); }
.grup-aufgabe-frist.is-ueberfaellig { color: var(--err); font-weight: var(--fw-fett); }
.grup-aufgaben-zahl { margin: 0 0 var(--sp-2); }
.grup-aufgaben-erledigt { margin-top: var(--sp-3); border-top: var(--rahmen-breite) solid var(--rahmen-farbe); padding-top: var(--sp-2); }
/* UI-R9b: der Einklapp-Knopf ist ein `DkButton` (ghost) — eigener Fokusring
   kommt aus der Bibliothek; hier steht nur, wie ruhig er aussieht. */
.grup-aufgaben-einklappen { color: var(--muted); font-size: var(--fs-sm); }
.grup-aufgaben-einklappen:hover { color: var(--text); }

.grup-link { color: var(--primary); font-size: var(--fs-sm); text-decoration: none; }
.grup-link:hover { text-decoration: underline; }

.grup-chips { display: flex; flex-wrap: wrap; gap: var(--sp-2); }
.grup-chip {
    display: inline-flex;
    align-items: center;
    padding: 2px 10px;
    border-radius: var(--badge-r);
    background: var(--surface-2);
    color: var(--muted);
    font-size: var(--fs-sm);
    font-weight: var(--fw-fett);
    text-decoration: none;
}
.grup-chip:hover { background: var(--surface-hover); color: var(--text); }

.grup-wert { color: var(--text); }
.grup-rechts { text-align: right; }

/* UX2e: Die Aktionsspalte trägt nur den „⋯"-Knopf — schmal halten, damit die
   Namensspalte den Platz behält. */
.dk-zeilen-aktion {
  width: var(--control-h);
  text-align: right;
}
</style>
