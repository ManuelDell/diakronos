<template>
    <div class="dk-screen dk-screen-enter">
        <!-- Seitenkopf -->
        <DkPageHeader
            :title="displayName"
            :sub="breadcrumb"
            :krumen="[{ text: 'Gruppen', href: '#/gruppen' }, { text: displayName }]"
            :badges="[{ text: currentStatus || 'Unbekannt', variant: statusVariante }]"
        >
            <template #actions>
                <div v-if="verantwortliche.length > 0" class="grup-avatar">
                    <img v-if="verantwortliche[0].foto" :src="verantwortliche[0].foto" :alt="verantwortliche[0].name" />
                    <span v-else>{{ initials(verantwortliche[0].name) }}</span>
                </div>
            </template>
        </DkPageHeader>

        <!-- OP-UI-19: Seitenkopf steht schon, der Inhalt ist ein Skelett statt
             eines nackten „Lade…“. -->
        <DkSkelett v-if="loading" form="zeilen" :anzahl="5" text="Gruppe wird geladen …" />

        <!-- Fehler -->
        <DkHint v-else-if="error" variant="err">{{ error }}</DkHint>

        <template v-else>
            <!-- Zweispaltig -->
            <div class="grup-grid">
                <!-- LINKE SPALTE -->
                <div class="grup-spalte">
                    <!-- Details -->
                    <DkCard title="Details">
                        <template #actions>
                            <DkButton v-if="canManage && !editingDesc" variant="ghost" size="sm" @click="startEditDesc" aria-label="Details bearbeiten">
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
                                <div class="grup-aktionen">
                                    <DkButton variant="primary" size="sm" :loading="savingDesc" @click="saveDesc">Speichern</DkButton>
                                    <DkButton variant="ghost" size="sm" @click="cancelEditDesc">Abbrechen</DkButton>
                                </div>
                            </div>
                        </template>
                    </DkCard>

                    <!-- P1-8 (OP-CHOR-3/OP-ADMIN-4): Verantwortliche pflegbar.
                         Nur wer verwalten darf, sieht die Karte — die Zuweisung
                         selbst prueft ohnehin der Server. -->
                    <VerantwortlicheKarte
                        v-if="canManage"
                        :doctype="isUntergruppe ? 'Untergruppe' : 'Gruppe'"
                        :name="gruppeId"
                        @gespeichert="fetchGruppe"
                    />

                    <!-- Termine -->
                    <DkCard title="Nächste Termine">
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
                            <DkButton v-if="canManage" variant="ghost" size="sm" @click="showAnkuendigungForm = !showAnkuendigungForm" aria-label="Ankündigung anlegen">
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
                            </DkButton>
                        </template>
                        <div v-if="showAnkuendigungForm" class="grup-formular grup-neu">
                            <input v-model="neueAnkuendigungTitel" type="text" placeholder="Titel" class="dk-ui-eingabe" />
                            <textarea v-model="neueAnkuendigungText" placeholder="Text (optional)" class="dk-ui-eingabe" rows="3" />
                            <div class="grup-aktionen">
                                <DkButton variant="primary" size="sm" :disabled="!neueAnkuendigungTitel.trim() || sendingAnkuendigung" :loading="sendingAnkuendigung" @click="createAnkuendigung">Veröffentlichen</DkButton>
                                <DkButton variant="ghost" size="sm" @click="showAnkuendigungForm = false; neueAnkuendigungTitel = ''; neueAnkuendigungText = ''">Abbrechen</DkButton>
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
                            <DkButton v-if="canManage" variant="ghost" size="sm" @click="showAufgabeInput = !showAufgabeInput" aria-label="Aufgabe anlegen">
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
                            </DkButton>
                        </template>
                        <div v-if="showAufgabeInput" class="grup-zeile">
                            <input v-model="neueAufgabe" type="text" placeholder="Neue Aufgabe…" class="dk-ui-eingabe" @keyup.enter="createAufgabe" />
                            <DkButton variant="primary" size="sm" :disabled="!neueAufgabe.trim() || sendingAufgabe" :loading="sendingAufgabe" @click="createAufgabe">Hinzufügen</DkButton>
                            <DkButton variant="ghost" size="sm" @click="showAufgabeInput = false; neueAufgabe = ''">✕</DkButton>
                        </div>
                        <DkEmpty v-if="aufgaben.length === 0" title="Keine Aufgaben vorhanden" icon="📋" />
                        <ul v-else class="grup-liste">
                            <li v-for="a in aufgaben" :key="a.name" class="grup-aufgabe">
                                <DkCheckbox :model-value="a.erledigt" @update:model-value="toggleAufgabe(a)" />
                                <span :class="['grup-aufgabe-titel', { 'is-erledigt': a.erledigt }]">{{ a.titel }}</span>
                                <span v-if="a.faellig && !a.erledigt" class="grup-eintrag-text">{{ formatDate(a.faellig) }}</span>
                            </li>
                        </ul>
                    </DkCard>

                    <!-- Wiki -->
                    <DkCard v-if="wikiArtikel.length > 0 || canManage" title="Wiki">
                        <template #actions>
                            <DkButton v-if="canManage" variant="ghost" size="sm" aria-label="Wiki-Artikel anlegen" @click="navigate('#/wiki')">
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
                    <tr v-for="m in mitglieder" :key="m.name || m.mitglied">
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
                        <td class="grup-rechts">
                            <DkButton variant="ghost" size="sm" @click="removeMitglied(m)">Entfernen</DkButton>
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
    </div>
</template>

<script>
import { ref, computed, onMounted, watch } from 'vue'
import { useSession } from '../composables/useSession.js'
import { getRouteParam, navigate } from '../router.js'
import { apiCall } from '../composables/useApi.js'
import { showToast } from '../composables/useToast.js'
import { bestaetigen } from '../composables/useBestaetigen.js'
import { useFormularSchutz } from '../composables/useFormularSchutz.js'
import { useVerlassenSchutz } from '../composables/useVerlassenSchutz.js'
import { darfProfilLink } from '../composables/geloeschte-person.mjs'
import DkPageHeader from '../components/ui/DkPageHeader.vue'
import DkButton from '../components/ui/DkButton.vue'
import DkBadge from '../components/ui/DkBadge.vue'
import DkCard from '../components/ui/DkCard.vue'
import DkField from '../components/ui/DkField.vue'
import DkSelect from '../components/ui/DkSelect.vue'
import DkCheckbox from '../components/ui/DkCheckbox.vue'
import DkTable from '../components/ui/DkTable.vue'
import DkEmpty from '../components/ui/DkEmpty.vue'
import DkHint from '../components/ui/DkHint.vue'
import DkSkelett from '../components/ui/DkSkelett.vue'
import MitgliedAuswahl from '../components/MitgliedAuswahl.vue'
// OP-CHOR-12/K2: kein Klammerplural — „1 Mitglied“, „3 Mitglieder“.
import { zahlWort } from '../components/ui/begriffe.mjs'
import VerantwortlicheKarte from '../components/VerantwortlicheKarte.vue'

export default {
    name: 'GruppeDetail',
    components: {
        DkPageHeader, DkButton, DkBadge, DkCard, DkField, DkSelect,
        DkCheckbox, DkTable, DkEmpty, DkHint, MitgliedAuswahl, VerantwortlicheKarte,
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
        const loading = ref(false)
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

        // Ankündigungen
        const showAnkuendigungForm = ref(false)
        const neueAnkuendigungTitel = ref('')
        const neueAnkuendigungText = ref('')
        const sendingAnkuendigung = ref(false)

        const gruppeId = computed(() => getRouteParam('id') || window.location.hash.split('/')[2] || '')

        // Prüfe ob es eine Untergruppe ist (Untergruppe DocType hat kein gruppenname, sondern untergruppenname)
        const isUntergruppe = computed(() => !!untergruppe.value)

        const displayName = computed(() => {
            if (untergruppe.value) return untergruppe.value.untergruppenname || untergruppe.value.name || 'Gruppe'
            return gruppe.value?.gruppenname || gruppe.value?.name || 'Gruppe'
        })

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
            { key: 'aktionen', label: 'Aktionen', numeric: true },
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

        async function fetchGruppe() {
            const id = gruppeId.value
            if (!id) return
            loading.value = true
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
            } catch (err) {
                error.value = err?.message || 'Fehler beim Laden'
            } finally {
                loading.value = false
            }
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
                    fetchGruppe()
                } else {
                    showToast('Fehler beim Speichern', 'error')
                }
            } catch (e) {
                showToast('Fehler beim Speichern', 'error')
            } finally {
                savingDesc.value = false
            }
        }

        // --- Aufgaben ---
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
                const res = await apiCall('diakronos.diakonos.api.gruppen.create_aufgabe', params)
                if (res?.success) {
                    neueAufgabe.value = ''
                    showAufgabeInput.value = false
                    showToast('Aufgabe erstellt', 'success')
                    fetchGruppe()
                } else {
                    showToast('Fehler beim Erstellen', 'error')
                }
            } catch (e) {
                showToast('Fehler beim Erstellen', 'error')
            } finally {
                sendingAufgabe.value = false
            }
        }

        async function toggleAufgabe(a) {
            try {
                const res = await apiCall('diakronos.diakonos.api.gruppen.toggle_aufgabe', { aufgabe_id: a.name })
                if (res?.success) {
                    a.erledigt = res.erledigt
                }
            } catch (e) {
                showToast('Fehler', 'error')
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
                    fetchGruppe()
                } else {
                    showToast('Fehler beim Erstellen', 'error')
                }
            } catch (e) {
                showToast('Fehler beim Erstellen', 'error')
            } finally {
                sendingAnkuendigung.value = false
            }
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
                    fetchGruppe()
                    return true
                }
                showToast(res?.message || 'Fehler beim Hinzufügen', 'error')
                return false
            } catch (err) {
                showToast(err?.message || 'Fehler beim Hinzufügen', 'error')
                return false
            }
        }

        async function removeMitglied(m) {
            const id = gruppeId.value
            const mitglied_id = m.mitglied || m.name
            if (!id || !mitglied_id) return
            if (!await bestaetigen({ titel: 'Mitglied entfernen?', text: 'Eine Person wird aus dieser Gruppe entfernt. Das Mitglied und seine anderen Gruppen bleiben erhalten.', aktion: 'Aus Gruppe entfernen', gefahr: true })) return
            try {
                const res = await apiCall('diakronos.diakonos.api.gruppen.remove_mitglied_from_gruppe', {
                    gruppe_id: id,
                    mitglied_id: mitglied_id,
                    is_untergruppe: isUntergruppe.value,
                })
                if (res?.success) {
                    showToast('Mitglied entfernt', 'success')
                    fetchGruppe()
                } else {
                    showToast(res?.message || 'Fehler beim Entfernen', 'error')
                }
            } catch (err) {
                showToast('Fehler beim Entfernen', 'error')
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
                    showToast(res?.message || 'Fehler beim Aktualisieren', 'error')
                }
            } catch (err) {
                showToast('Fehler beim Aktualisieren', 'error')
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
            // DSGVO-2d: eine gelöschte Person hat kein Profil (kein Link).
            darfProfilLink,
            // OP-CHOR-12/K2: Numerus-Helfer für „1 Mitglied“/„3 Mitglieder“.
            zahlWort,
            gruppe,
            untergruppe,
            mitglieder,
            verantwortliche,
            untergruppen,
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
            editingDesc,
            editName,
            editDesc,
            editTreffpunkt,
            editTreffzeit,
            savingDesc,
            showAufgabeInput,
            neueAufgabe,
            sendingAufgabe,
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
            ladeMitgliederAuswahl,
            mitgliedAusgewaehlt,
            removeMitglied,
            updateRolle,
            // B-3: `navigate('#/wiki')` steht im Template (Options-API ohne
            // <script setup>, keine globalProperties) — ohne diese Zeile war
            // der Wiki-Knopf `undefined` und der Klick warf einen TypeError.
            navigate,
        }
    },
}
</script>

<style scoped>
.grup-grid {
    display: grid;
    grid-template-columns: 2fr 1fr;
    gap: var(--sp-4);
}
.grup-spalte { display: flex; flex-direction: column; gap: var(--sp-4); }
.grup-breit { margin-top: var(--sp-4); }
@media (max-width: 768px) {
    .grup-grid { grid-template-columns: 1fr; }
}

.grup-zustand { padding: var(--sp-8); text-align: center; color: var(--muted); }
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
.grup-datenwert { color: var(--text); text-align: right; }

.grup-formular { display: flex; flex-direction: column; gap: var(--sp-3); }
.grup-neu { margin-bottom: var(--sp-4); padding: var(--sp-3); border: 1px solid var(--line); border-radius: var(--radius); background: var(--surface-2); }
.grup-aktionen { display: flex; gap: var(--sp-2); flex-wrap: wrap; }
.grup-zeile { display: flex; gap: var(--sp-2); align-items: flex-end; }
.grup-zeile .dk-ui-eingabe { flex: 1; }
.grup-zeile-abstand { margin-bottom: var(--sp-4); }

.grup-termine { display: flex; gap: var(--sp-3); flex-wrap: wrap; }
.grup-termin {
    flex: 1;
    min-width: 120px;
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
    font-weight: 600;
    flex-shrink: 0;
    overflow: hidden;
}
.grup-avatar img { width: 100%; height: 100%; object-fit: cover; }

.grup-liste { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: var(--sp-2); }
.grup-eintrag { padding: var(--sp-3); border: 1px solid var(--line); border-radius: var(--radius); background: var(--surface-2); }
.grup-eintrag-kopf { display: flex; align-items: center; gap: var(--sp-2); margin-bottom: var(--sp-1); }
.grup-eintrag-titel { font-weight: 500; color: var(--text); font-size: var(--fs-sm); }
.grup-eintrag-text { font-size: var(--fs-xs); color: var(--muted); margin: 0; }

.grup-aufgabe { display: flex; align-items: center; gap: var(--sp-3); padding: var(--sp-2) 0; border-bottom: 1px solid var(--line); }
.grup-aufgabe:last-child { border-bottom: none; }
.grup-aufgabe-titel { flex: 1; font-size: var(--fs-sm); color: var(--text); }
.grup-aufgabe-titel.is-erledigt { text-decoration: line-through; color: var(--muted); }

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
    font-weight: 600;
    text-decoration: none;
}
.grup-chip:hover { background: var(--surface-hover); color: var(--text); }

.grup-wert { color: var(--text); }
.grup-rechts { text-align: right; }
</style>
