<template>
    <div class="org-ansicht">
        <div v-if="kopfzeile" class="org-kopf">
            <p class="org-hinweis">
                Jeder Kasten ist ein Dienstbereich, eine Gruppe oder eine Untergruppe.
                Antippen öffnet die Gruppe, der Stift bearbeitet sie.
            </p>
            <DkButton
                v-if="hasEditableGroups || perms.can_create_any"
                variant="secondary"
                @click="openManageModal"
            >Gruppen verwalten</DkButton>
        </div>

        <div v-if="loading" class="org-zustand">Lade…</div>

        <div v-else-if="nodes.length <= 1" class="org-leer">
            <DkEmpty title="Noch keine Gruppen vorhanden"
                     text="Sobald Gruppen angelegt sind, erscheint hier die Struktur der Gemeinde."
                     icon="🌳" />
        </div>

        <div
            v-else
            class="org-scroll"
        >
            <div id="dk-org-chart" class="org-chart"></div>
        </div>
    </div>

    <!-- Verwalten (Schritt 1) -->
    <DkDialog v-model="showManageModal" title="Gruppen verwalten">
        <p class="org-hinweis">Was möchtest du tun?</p>
        <div class="org-optionen">
            <div class="org-option" @click="goToEdit">
                <span class="org-option-icon">✏️</span>
                <div>
                    <div class="org-option-titel">Gruppe bearbeiten</div>
                    <div class="org-option-text">Name, Treffzeit, Beschreibung ändern</div>
                </div>
            </div>
            <div class="org-option" @click="goToCreate">
                <span class="org-option-icon">➕</span>
                <div>
                    <div class="org-option-titel">Neue Gruppe erstellen</div>
                    <div class="org-option-text">Gruppe, Untergruppe oder Dienstbereich anlegen</div>
                </div>
            </div>
        </div>
        <template #footer>
            <DkButton variant="ghost" @click="closeManageModal">Abbrechen</DkButton>
        </template>
    </DkDialog>

    <!-- Bearbeiten: Auswahl (Schritt 2a) -->
    <DkDialog v-model="showEditSelectModal" title="Gruppe bearbeiten">
        <DkField label="Gruppe auswählen">
            <DkSelect v-model="editSelectId" :options="editableNodeOptionen" placeholder="— Bitte wählen —" />
        </DkField>
        <template #footer>
            <DkButton variant="secondary" @click="closeEditSelectModal">Zurück</DkButton>
            <DkButton variant="primary" :disabled="!editSelectId" @click="proceedToEdit">Weiter</DkButton>
        </template>
    </DkDialog>

    <!-- Bearbeiten (Schritt 2a final) -->
    <DkDialog v-model="showEditModal" title="Bearbeiten">
        <!-- OP-UI-23: Enter im Feld speichert (wie der Knopf). -->
        <form class="org-formular" @submit.prevent="submitEdit">
            <DkField label="Name" required :error="editFehler.name">
                <input v-model="editForm.name" type="text" class="dk-ui-eingabe" required />
            </DkField>
            <DkField label="Beschreibung">
                <textarea v-model="editForm.beschreibung" class="dk-ui-eingabe" rows="3"></textarea>
            </DkField>
            <!-- OP-UI-20: Treffzeit als Wochentag + Uhrzeit statt Freitext.
                 Gespeichert bleibt der bisherige Text („Dienstag 19:30“),
                 damit alte Werte gültig bleiben. -->
            <DkField label="Treffzeit" help="Wochentag und Uhrzeit des regelmäßigen Treffens">
                <div class="org-treffzeit">
                    <select v-model="treffzeitTag" class="dk-ui-eingabe" aria-label="Wochentag">
                        <option value="">— kein Wochentag —</option>
                        <option v-for="t in WOCHENTAGE" :key="t" :value="t">{{ t }}</option>
                    </select>
                    <input v-model="treffzeitUhr" type="time" step="60" class="dk-ui-eingabe" aria-label="Uhrzeit" />
                </div>
            </DkField>
            <p v-if="treffzeitNichtRhythmus()" class="org-treffzeit-hinweis">
                Bisheriger Eintrag: „{{ editForm.treffzeit }}“. Er bleibt so
                gespeichert, solange du oben nichts auswählst. Wählst du nur
                einen Wochentag oder nur eine Uhrzeit, ersetzt das den
                bisherigen Eintrag ganz.
            </p>
            <DkField label="Treffpunkt">
                <input v-model="editForm.treffpunkt" type="text" class="dk-ui-eingabe" placeholder="z.B. Gemeindesaal" />
            </DkField>
        </form>
        <template #footer>
            <DkButton variant="ghost" @click="closeEditModal">Abbrechen</DkButton>
            <DkButton variant="primary" :disabled="sendingEdit" :loading="sendingEdit" @click="submitEdit">Speichern</DkButton>
        </template>
    </DkDialog>

    <!-- Erstellen (Schritt 2b) -->
    <DkDialog v-model="showCreateModal" title="Neue Gruppe / Untergruppe">
        <!-- OP-UI-23: Enter im Feld erstellt (wie der Knopf). -->
        <form class="org-formular" @submit.prevent="submitCreate">
            <DkField label="Typ">
                <DkSelect v-model="createForm.typ" :options="typOptionen" />
            </DkField>
            <DkField label="Name" required :error="createFehler.name">
                <input v-model="createForm.name" type="text" class="dk-ui-eingabe" placeholder="Name eingeben" required />
            </DkField>
            <DkField v-if="createForm.typ === 'gruppe'" label="Dienstbereich" required :error="createFehler.parent">
                <DkSelect v-model="createForm.parent" :options="dienstbereichOptionen" placeholder="Bitte wählen" />
            </DkField>
            <DkField v-if="createForm.typ === 'untergruppe'" label="Gruppe" required :error="createFehler.parent">
                <DkSelect v-model="createForm.parent" :options="gruppenOptionen" placeholder="Bitte wählen" />
            </DkField>
            <DkField v-if="createForm.typ === 'dienstbereich'" label="Farbe (optional)" help="Farbe im Farbwähler aussuchen — gespeichert wird ein Hex-Wert.">
                <div class="org-farbwahl">
                    <input v-model="createForm.farbe" type="color" class="org-farbwahl-feld" aria-label="Farbe des Dienstbereichs" />
                    <span class="org-farbwahl-wert">{{ createForm.farbe || 'Standardfarbe' }}</span>
                </div>
            </DkField>
        </form>
        <template #footer>
            <DkButton variant="ghost" @click="closeCreateModal">Abbrechen</DkButton>
            <DkButton variant="primary" :disabled="sendingCreate" :loading="sendingCreate" @click="submitCreate">Erstellen</DkButton>
        </template>
    </DkDialog>
</template>

<script setup>
/**
 * N13 — Organigramm als Ansicht in „Gruppen“.
 *
 * Das Organigramm war früher eine eigene Seite (#/organigramm). Seit der
 * Neuordnung ist es die zweite Ansicht der Seite „Gruppen“; der Umschalter
 * Liste/Organigramm steht in Gruppen.vue, die Adresse lautet
 * `#/gruppen/organigramm` (die alte Adresse leitet im Router hierher um).
 *
 * Die Darstellung (d3-org-chart) ist unverändert aus `pages/Organigramm.vue`
 * übernommen: dieselben sicheren Helfer aus `shared/sichere-ausgabe.js`
 * (P0-5/P0-5b — kein Fremdwert landet roh im Markup), dieselben Backend-
 * Aufrufe und dieselben Rechte wie auf der Gruppenseite.
 */
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { OrgChart } from 'd3-org-chart'
import { apiCall } from '../../composables/useApi.js'
// UXD-R5: escapeHtml/sichereFarbe kommen aus EINER gemeinsamen Quelle — die
// zweite Organigramm-Oberflaeche (organigramm/App.vue) nutzt dieselben Helfer.
import { escapeHtml, sichereFarbe, STANDARD_FARBE } from '../../../shared/sichere-ausgabe.js'
import { showToast } from '../../composables/useToast.js'
import DkButton from '../ui/DkButton.vue'
import DkDialog from '../ui/DkDialog.vue'
import { baueTreffzeit, WOCHENTAGE } from '../../composables/treffzeit.mjs'
import DkField from '../ui/DkField.vue'
import DkSelect from '../ui/DkSelect.vue'
import DkEmpty from '../ui/DkEmpty.vue'

const props = defineProps({
    // In der Gruppenansicht steht der Seitenkopf in Gruppen.vue; die kleine
    // Bedienzeile (Hinweis + „Gruppen verwalten“) bleibt hier.
    kopfzeile: { type: Boolean, default: true },
    // N13: die Ansicht sitzt eingebettet im Gruppen-Bereich — der eigene
    // Seitenkopf entfällt dann.
    embedded: { type: Boolean, default: false },
})

const loading = ref(true)
const nodes = ref([])
const perms = ref({ can_create_dienstbereich: false, can_create_any: false, can_edit_ids: [] })
let chart = null

// UXD-R4/OP-ADMIN-5: Kan-Listen arbeiten mit den ROhen Namen (backend liefert
// can_edit_ids ohne Präfix), die Knoten tragen sie als `raw_name`.
function roherName(node) {
  if (!node) return ''
  return node.raw_name || node.id || ''
}

const hasEditableGroups = computed(() => perms.value.can_edit_ids?.length > 0)

const dienstbereiche = computed(() => nodes.value.filter(n => n.type === 'dienstbereich'))
const gruppenNodes = computed(() => nodes.value.filter(n => n.type === 'gruppe'))
const editableNodes = computed(() => nodes.value.filter(n => perms.value.can_edit_ids?.includes(roherName(n))))

/* Bausteine beschicken */
const typOptionen = [
  { value: 'gruppe', label: 'Gruppe' },
  { value: 'untergruppe', label: 'Untergruppe' },
  { value: 'dienstbereich', label: 'Dienstbereich' },
]
const editableNodeOptionen = computed(() =>
  editableNodes.value.map(n => ({ value: roherName(n), label: `${n.name} (${n.type})` })))
// Die Auswahlwerte sind die ROhen Namen — das Backend erwartet sie so; die
// früheren Präfixe db_/g_ führten zu ForeignKeyViolation bzw. 404.
const dienstbereichOptionen = computed(() =>
  dienstbereiche.value.map(db => ({ value: roherName(db), label: db.name })))
const gruppenOptionen = computed(() =>
  gruppenNodes.value.map(g => ({ value: roherName(g), label: g.name })))

/* ---------- Modals ---------- */
const showManageModal = ref(false)
const showEditSelectModal = ref(false)
const showEditModal = ref(false)
const showCreateModal = ref(false)

const editSelectId = ref('')
// UXD-R28: der Farbwaehler hat immer einen Wert. Der Startwert kommt aus dem
// Token-System (--dk-brand-500) statt aus einem festen Farbwert — der
// Waechter-Test verbietet Klartext-Farben in dieser Datei. Liefert das Token
// keinen auswertbaren Hex (z. B. oklch()), greift der Standardwert aus dem
// gemeinsamen Modul — sonst zeigt der Waehler Schwarz, obwohl daneben
// "Standardfarbe" steht.
const FARB_TREFFER = /#([0-9a-fA-F]{6})\b/
function standardFarbe() {
    const wert = (typeof getComputedStyle === 'function')
        ? getComputedStyle(document.documentElement).getPropertyValue('--dk-brand-500').trim()
        : ''
    const m = FARB_TREFFER.exec(wert)
    // Der Farbwaehler braucht zwingend #RRGGBB.
    return m ? '#' + m[1] : STANDARD_FARBE
}
const createForm = ref({ typ: 'gruppe', name: '', parent: '', farbe: standardFarbe() })
const sendingCreate = ref(false)
const sendingEdit = ref(false)
// OP-UI-5/UXD-R22: Fehler am Feld statt Browser-Blase / stillem Nichtstun.
const createFehler = ref({ name: '', parent: '' })

const editTarget = ref(null)
const editForm = ref({ name: '', beschreibung: '', treffzeit: '', treffpunkt: '' })

// OP-UI-20: Treffzeit aus zwei Feldern. Der gespeicherte Text bleibt die
// Wahrheit (alte Werte wie „nach Absprache“ gehen nicht verloren).
const treffzeitTag = ref('')
const treffzeitUhr = ref('')

/** R-DES-REST-b W-1: Den gespeicherten Eintrag IMMER zeigen, sobald es einen gibt —
 *  die Felder starten leer, sonst waere der Altwert („Mo 07:00“) unsichtbar. */
function treffzeitNichtRhythmus() {
    return !!editForm.value.treffzeit
}

/**
 * B2/W2: Die beiden Felder beschreiben NUR, was der Nutzer selbst ausgewählt
 * hat. Solange er sie nicht anfasst, bleibt der gespeicherte Text Zeichen für
 * Zeichen stehen — sonst würde aus „jeden 2. Dienstag im Monat, 19:30“ beim
 * Speichern irgendeines anderen Feldes „Dienstag 19:30“.
 *
 * Ein Alteintrag wird deshalb NICHT beim Öffnen in die Felder zerlegt; die
 * Felder starten leer und stehen nur für eine bewusste Änderung bereit.
 */
function treffzeitAusFeldern() {
    // Nur eine ANGEKLICKTE Eingabe zählt. Ein „verlustfreier Rückbau“ wäre
    // hier kein Ausweg: „jeden 2. Dienstag im Monat, 19:30“ wird als
    // „Dienstag“ + „19:30“ zerlegt, aus dem Zerlegten gebaut ergäbe aber
    // „Dienstag 19:30“ — also gerade NICHT den Ausgangstext.
    const gebaut = baueTreffzeit(treffzeitTag.value, treffzeitUhr.value)
    if (!gebaut) return editForm.value.treffzeit || ''
    return gebaut
}

const editFehler = ref({ name: '' })

function openManageModal() {
    showManageModal.value = true
}
function closeManageModal() {
    showManageModal.value = false
}

function goToEdit() {
    closeManageModal()
    // R-DES-REST-b Nebenbefund: Genau EINE bearbeitbare Gruppe → direkt in das
    // Bearbeiten-Fenster, statt sie im Auswahlfeld zu suchen. Bisher war dieser
    // Weg der einzige, der funktionierte.
    if (editableNodes.value.length === 1) {
        editSelectId.value = roherName(editableNodes.value[0])
        proceedToEdit()
        return
    }
    editSelectId.value = ''
    showEditSelectModal.value = true
}
function goToCreate() {
    closeManageModal()
    createForm.value = { typ: 'gruppe', name: '', parent: '', farbe: standardFarbe() }
    createFehler.value = { name: '', parent: '' }
    showCreateModal.value = true
}

function closeEditSelectModal() {
    showEditSelectModal.value = false
    editSelectId.value = ''
}

function proceedToEdit() {
    if (!editSelectId.value) return
    const node = editableNodes.value.find(n => roherName(n) === editSelectId.value)
    if (!node) return
    editTarget.value = node
    editFehler.value = { name: '' }
    editForm.value = {
        name: node.name || '',
        beschreibung: node.beschreibung || '',
        treffzeit: node.treffzeit || '',
        treffpunkt: node.treffpunkt || ''
    }
    // W2: NICHT aus dem Alteintrag vorbelegen. Die Felder starten leer und
    // aendern den Text nur, wenn der Nutzer selbst etwas auswaehlt.
    treffzeitTag.value = ''
    treffzeitUhr.value = ''
    showEditSelectModal.value = false
    showEditModal.value = true
}

function closeCreateModal() {
    showCreateModal.value = false
}

function closeEditModal() {
    showEditModal.value = false
    editTarget.value = null
}

async function submitCreate() {
    if (sendingCreate.value) return
    const f = createForm.value
    // OP-UI-5/UXD-R22: Fehler am Feld (statt Browser-Blase oder stillem
    // Nichtstun) und Fokus ins erste fehlende Feld.
    const fehler = { name: '', parent: '' }
    if (!f.name.trim()) fehler.name = 'Bitte einen Namen angeben.'
    if (f.typ !== 'dienstbereich' && !f.parent) {
        fehler.parent = f.typ === 'untergruppe'
            ? 'Bitte eine Gruppe wählen.'
            : 'Bitte einen Dienstbereich wählen.'
    }
    createFehler.value = fehler
    if (fehler.name || fehler.parent) {
        requestAnimationFrame(() => document.querySelector('.org-formular .dk-ui-eingabe')?.focus())
        return
    }
    sendingCreate.value = true
    try {
        if (f.typ === 'dienstbereich') {
            await apiCall('diakronos.diakonos.api.gruppen.create_dienstbereich', {
                name: f.name.trim(),
                farbe: f.farbe || standardFarbe()
            })
            showToast('Dienstbereich angelegt', 'success') // OP-ADMIN-22
        } else if (f.typ === 'gruppe') {
            // UXD-R4: das Backend verlangt `dienstbereich` (nicht `parent`).
            await apiCall('diakronos.diakonos.api.gruppen.create_gruppe', {
                name: f.name.trim(),
                dienstbereich: f.parent
            })
            showToast('Gruppe angelegt', 'success')
        } else if (f.typ === 'untergruppe') {
            // UXD-R4: das Backend verlangt `gruppe` (nicht `parent`).
            await apiCall('diakronos.diakonos.api.gruppen.create_untergruppe', {
                name: f.name.trim(),
                gruppe: f.parent
            })
            showToast('Untergruppe angelegt', 'success')
        }
        closeCreateModal()
        await loadData()
    } catch (err) {
        console.error('Fehler beim Erstellen:', err)
        showToast('Fehler beim Erstellen: ' + (err.message || 'Unbekannter Fehler'), 'error')
    } finally {
        sendingCreate.value = false
    }
}

async function submitEdit() {
    if (!editTarget.value || sendingEdit.value) return
    // OP-ADMIN-5/UXD-R22: leerer Name wird am Feld benannt.
    if (!editForm.value.name.trim()) {
        editFehler.value = { name: 'Bitte einen Namen angeben.' }
        requestAnimationFrame(() => document.querySelector('.org-formular .dk-ui-eingabe')?.focus())
        return
    }
    editFehler.value = { name: '' }
    sendingEdit.value = true
    try {
        const name = roherName(editTarget.value)
        const typ = editTarget.value.type
        // UXD-R4/OP-ADMIN-5: Feldname je Typ (Gruppe `gruppenname`,
        // Untergruppe `untergruppenname`, Dienstbereich `ministry`) und die
        // richtige Methode mit den richtigen Argumenten.
        if (typ === 'gruppe') {
            await apiCall('diakronos.diakonos.api.gruppen.update_gruppe', {
                name,
                gruppenname: editForm.value.name.trim(),
                beschreibung: editForm.value.beschreibung,
                treffzeit: treffzeitAusFeldern(),
                treffpunkt: editForm.value.treffpunkt
            })
        } else if (typ === 'untergruppe') {
            await apiCall('diakronos.diakonos.api.gruppen.update_untergruppe', {
                name,
                untergruppenname: editForm.value.name.trim(),
                beschreibung: editForm.value.beschreibung,
                treffzeit: treffzeitAusFeldern(),
                treffpunkt: editForm.value.treffpunkt
            })
        } else if (typ === 'dienstbereich') {
            await apiCall('diakronos.diakonos.api.gruppen.update_dienstbereich', {
                name,
                ministry: editForm.value.name.trim(),
                beschreibung: editForm.value.beschreibung
            })
        }
        showToast('Gespeichert', 'success')
        closeEditModal()
        await loadData()
    } catch (err) {
        console.error('Fehler beim Speichern:', err)
        showToast('Fehler beim Speichern: ' + (err.message || 'Unbekannter Fehler'), 'error')
    } finally {
        sendingEdit.value = false
    }
}

/* ---------- d3-org-chart ---------- */
// UXD-R5/UXD-R28: escapeHtml() und sichereFarbe() liegen in
// `shared/sichere-ausgabe.js` — dieselben Helfer nutzt die zweite
// Organigramm-Oberflaeche (organigramm/App.vue). Keine Kopien hier.

function buildNodeContent(d) {
    if (d.data.type === 'root') {
        return '<div style="width:1px;height:1px;overflow:hidden;opacity:0;"></div>'
    }
    const t = d.data.type
    const isDB = t === 'dienstbereich'
    const isUG = t === 'untergruppe'

    let nodeWidth = 220
    let nodeHeight = 80
    if (isDB) { nodeWidth = 200; nodeHeight = 60 }
    else if (t === 'gruppe') { nodeWidth = 190; nodeHeight = 72 }
    else if (isUG) { nodeWidth = 170; nodeHeight = 64 }

    const farbe = sichereFarbe(d.data.farbe)
    const borderLeft = farbe ? `border-left:3px solid ${farbe};` : ''
    const bg = isDB ? 'background:var(--surface-2);' : 'background:var(--surface);'
    const boxShadow = isDB ? 'box-shadow:var(--shadow);' : ''
    const borderRadius = 'border-radius:var(--radius);'
    const cursor = isDB ? '' : 'cursor:pointer;'
    const fontWeight = isDB ? '700' : '600'
    const fontSize = isUG ? '0.78rem' : (isDB ? '0.88rem' : '0.82rem')
    const padding = isDB ? '8px 14px' : '10px 12px'

    // id/type nur escapen, wenn sie im Markup landen; die onclick-Aufrufe
    // erhalten reine JS-Strings (JSON.stringify) statt roher Interpolation.
    const idJs = escapeHtml(JSON.stringify(String(d.data.id ?? '')))
    const typeJs = escapeHtml(JSON.stringify(String(d.data.type ?? '')))
    // REST-3: Die Detailseite erwartet den ROHEN Namen („Eheberatung“), nicht
    // die Knoten-Kennung („g_Eheberatung“) — sonst kam im Organigramm
    // „Gruppe 'g_Eheberatung' existiert nicht“. Dieselbe Quelle wie der Stift.
    const rawJs = escapeHtml(JSON.stringify(String(d.data.raw_name || d.data.id || '')))

    // P1-7: die Editierbarkeit prueft gegen den rohen Namen (raw_name), weil
    // can_edit_ids Rohnamen ohne Praefix fuehrt; der Aufruf selbst bekommt
    // weiterhin den escaped JS-String (P0-5/DES-04).
    // REST-3: Der Stift sitzt im Kasten, dessen onclick die Gruppe oeffnet.
    // Ohne stopPropagation lief der Klick zusaetzlich zum Kasten und die Seite
    // sprang auf die Detailansicht, statt zu bearbeiten (Befund REST-3).
    const editBtn = perms.value.can_edit_ids?.includes(d.data.raw_name || d.data.id)
        ? `<button onclick="event.stopPropagation(); window.__orgEditNode(${idJs})" style="position:absolute;top:6px;right:6px;background:none;border:none;cursor:pointer;font-size:0.75rem;color:var(--muted);">✏️</button>`
        : ''
    const memberLine = (!isDB && d.data.mitglieder_count !== undefined)
        ? `<div style="font-size:0.72rem;color:var(--muted);margin-top:4px;">👤 ${escapeHtml(d.data.mitglieder_count)}</div>`
        : ''
    const timeLine = d.data.treffzeit
        ? `<div style="font-size:0.7rem;color:var(--subtle);margin-top:2px;">🕐 ${escapeHtml(d.data.treffzeit)}</div>`
        : ''
    return `<div style="width:${d.width}px;height:${d.height}px;padding:${padding};box-sizing:border-box;border:1px solid var(--line);${bg}${borderLeft}${boxShadow}${borderRadius}${cursor}position:relative;overflow:hidden;"
        onclick="window.__orgNavigateNode(${idJs}, ${typeJs}, ${rawJs})">
        ${editBtn}
        <div style="font-weight:${fontWeight};font-size:${fontSize};color:var(--text);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${escapeHtml(d.data.name || d.data.id)}</div>
        ${memberLine}
        ${timeLine}
    </div>`
}

// N13: auf schmalen Geraeten passen die breiten Kaesten nicht nebeneinander.
// Dann werden die Kaesten schmaler gezeichnet (die Beschriftung kuerzt ohnehin
// mit „…"), statt den Baum abzuschneiden. Die Rechner-Ansicht bleibt wie zuvor.
function schmalerRahmen() {
    return typeof window !== 'undefined' && window.innerWidth > 0 && window.innerWidth < 560
}

function knotenBreite(d) {
    const schmal = schmalerRahmen()
    if (d.data.type === 'root') return 1
    if (d.data.type === 'dienstbereich') return schmal ? 140 : 200
    if (d.data.type === 'gruppe') return schmal ? 132 : 190
    if (d.data.type === 'untergruppe') return schmal ? 116 : 170
    return 220
}

async function renderChart() {
    await nextTick()
    const container = document.getElementById('dk-org-chart')
    if (!container) return
    if (chart) {
        chart.clear()
        chart = null
    }
    chart = new OrgChart()
    // Die Fenster-Ereignisse, die `render()` der Bibliothek anmeldet, werden
    // mitgeschrieben, damit sie beim Abbau zuverlaessig abgemeldet werden
    // koennen (siehe `loeseFensterBindungen`).
    merkeFensterBindungen(() => chart
        .container('#dk-org-chart')
        .data(nodes.value)
        .nodeWidth(knotenBreite)
        .nodeHeight(d => {
            if (d.data.type === 'root') return 1
            if (d.data.type === 'dienstbereich') return 60
            if (d.data.type === 'gruppe') return 72
            if (d.data.type === 'untergruppe') return 64
            return 80
        })
        .childrenMargin(() => 40)
        .compactMarginBetween(() => 15)
        .compactMarginPair(() => 40)
        .nodeContent(buildNodeContent)
        .render())

    // N13: auf schmalen Geraeten ist der Baum breiter als das Fenster (die
    // Kästen sind 170–220px breit und stehen in zwei Spalten). Statt die
    // äusseren Kästen abzuschneiden, wird der Baum dann auf die Rahmenbreite
    // skaliert (`fit`), sodass alle Dienstbereiche/Gruppen sichtbar sind. Auf
    // dem Rechner bleibt alles wie bisher (dort passt der Baum ohnehin).
    await nextTick()
    const rahmen = container.clientWidth
    const g = container.querySelector('svg > g')
    const baumBreite = g ? g.getBoundingClientRect().width : 0
    if (baumBreite > rahmen) {
        chart.fit({ animate: false, scale: true })
    }
}

async function loadData() {
    loading.value = true
    try {
        const [chartData, permsData] = await Promise.all([
            apiCall('diakronos.diakonos.api.gruppen.get_gruppen_for_orgchart'),
            apiCall('diakronos.diakonos.api.gruppen.get_user_create_permissions')
        ])
        nodes.value = chartData?.nodes || []
        perms.value = permsData || {}
        loading.value = false
        if (nodes.value.length > 1) {
            await renderChart()
        }
    } catch (err) {
        console.error('Fehler beim Laden:', err)
        loading.value = false
    }
}

onMounted(loadData)

/**
 * N13: das Organigramm ist jetzt eine Ansicht INNERHALB der Seite Gruppen.
 * Beim Umschalten auf die Liste wird diese Komponente abgebaut, waehrend
 * d3-org-chart noch an seinem Fenster-Ereignis haengt
 * (`resize.ID<zahl>`, siehe `render()` der Bibliothek). Dieses Ereignis greift
 * in `B.select(container).node()` auf den bereits entfernten Zeichenbereich zu
 * und wirft dann `Cannot read properties of null (reading
 * 'getBoundingClientRect')` — der Fehler erscheint, sobald sich danach das
 * Fenster aendert (Groessenaenderung, Drehen des Geraets, Umschalten
 * Desktop/Mobil) und der Handler einer abgebauten Ansicht noch im Speicher
 * liegt.
 *
 * `clear()` der Bibliothek raeumt den SVG-Baum ab und meldet `resize.<id>`
 * selbst wieder ab; `fullscreenchange.<id>` (auf `document`) bleibt jedoch
 * bestehen. Zusaetzlich koennen kurzlebige Anmeldungen des Bibliotheks-Renderers
 * uebrig bleiben. Deshalb protokolliert diese Komponente waehrend des Zeichnens
 * JEDE Anmeldung (am Fenster UND am Dokument) samt ihrer Zuhoerer-Funktion und
 * meldet sie beim Abbau mit GENAU DIESER Funktion wieder ab.
 *
 * Wichtig (Befund R-N2-code H1): Ein `removeEventListener(typ, null)` entfernt
 * NICHTS — es muss dieselbe Funktionsreferenz uebergeben werden, die angemeldet
 * wurde. d3-selection reicht die Zuhoerer-Funktion als zweites Argument an
 * `addEventListener` weiter; deshalb merkt sich das Protokoll `[ziel, typ, fn]`.
 */
const FENSTER_EREIGNISSE = ['resize', 'scroll', 'click', 'keydown', 'mousemove', 'touchstart',
    'fullscreenchange']
let fensterBindungen = []

/** Zielobjekte, an denen die Bibliothek Ereignisse anmeldet. */
function _ereignisZiele() {
    return [window, document]
}

/**
 * Ersetzt `addEventListener`/`removeEventListener` beider Ziele nur so lange,
 * wie der Baum gezeichnet wird, und protokolliert jede Anmeldung samt
 * Funktion. Danach werden die Originalfunktionen wiederhergestellt — die Seite
 * verhaelt sich also unveraendert.
 */
function merkeFensterBindungen(fn) {
    const originale = _ereignisZiele().map(z => [z, z.addEventListener, z.removeEventListener])
    for (const [ziel, add] of originale) {
        ziel.addEventListener = function (typ, ...rest) {
            if (typeof typ === 'string' && FENSTER_EREIGNISSE.includes(typ.split('.')[0])) {
                fensterBindungen.push([ziel, typ, rest[0]])
            }
            return add.call(this, typ, ...rest)
        }
    }
    for (const [ziel, , remove] of originale) {
        ziel.removeEventListener = function (typ, ...rest) {
            fensterBindungen = fensterBindungen.filter(
                ([z, t, f]) => !(z === ziel && t === typ
                    && (f === rest[0] || rest[0] === undefined))
            )
            return remove.call(this, typ, ...rest)
        }
    }
    try {
        return fn()
    } finally {
        for (const [ziel, add, remove] of originale) {
            ziel.addEventListener = add
            ziel.removeEventListener = remove
        }
    }
}

/** Meldet die protokollierten Anmeldungen mit ihrer Funktion wieder ab. */
function loeseFensterBindungen() {
    for (const [ziel, typ, fn] of fensterBindungen) {
        ziel.removeEventListener(typ, fn)
    }
    fensterBindungen = []
}

onBeforeUnmount(() => {
    if (chart) {
        chart.clear()
        chart = null
    }
    loeseFensterBindungen()
})

/* ---------- Globale Handler fuer inline HTML ---------- */
window.__orgEditNode = (id) => {
    const node = nodes.value.find(n => n.id === id)
    if (!node) return
    editTarget.value = node
    editFehler.value = { name: '' }
    editForm.value = {
        name: node.name || '',
        beschreibung: node.beschreibung || '',
        treffzeit: node.treffzeit || '',
        treffpunkt: node.treffpunkt || ''
    }
    // W2: NICHT aus dem Alteintrag vorbelegen. Die Felder starten leer und
    // aendern den Text nur, wenn der Nutzer selbst etwas auswaehlt.
    treffzeitTag.value = ''
    treffzeitUhr.value = ''
    showEditModal.value = true
}

window.__orgNavigateNode = (id, type, rawName) => {
    if (type === 'root' || type === 'dienstbereich') return
    // REST-3: Die Adresse trägt den rohen Namen — die Detailseite sucht ihn so
    // beim Server (`get_gruppe_detail`); `g_`/`ug_` gibt es dort nicht.
    const knoten = nodes.value.find(n => n.id === id)
    const ziel = rawName || (knoten ? roherName(knoten) : id)
    if (!ziel) return
    window.location.hash = '#/gruppe/' + encodeURIComponent(ziel)
}
</script>

<style scoped>
/* OP-UI-20: Treffzeit = Wochentag + Uhrzeit in einer Zeile. */
.org-treffzeit { display: flex; gap: var(--sp-2); flex-wrap: wrap; }
.org-treffzeit > select { flex: 1 1 140px; min-width: 0; }
.org-treffzeit > input { flex: 0 0 auto; min-width: 118px; }
.org-treffzeit-hinweis { margin: 0; font-size: var(--fs-sm); color: var(--muted); }

#dk-org-chart :deep(svg) {
    background: transparent !important;
}
#dk-org-chart :deep(.node) {
    cursor: default;
}
.org-ansicht { display: flex; flex-direction: column; gap: var(--sp-3); }
.org-kopf { display: flex; align-items: center; justify-content: space-between; gap: var(--sp-3); flex-wrap: wrap; }
/* N13: der Baum skaliert auf schmalen Geraeten auf die Rahmenbreite (siehe
   renderChart); der Rahmen bleibt als Sicherheit waagerecht rollbar. */
.org-scroll { overflow-x: auto; }
.org-chart { width: 100%; height: calc(100vh - 260px); overflow: hidden; }
.org-zustand { padding: 40px; text-align: center; color: var(--muted); }
.org-leer { padding: var(--sp-4) 0; }
.org-hinweis { margin: 0; color: var(--muted); font-size: var(--fs-sm); }
.org-optionen { display: flex; flex-direction: column; gap: var(--sp-3); }
.org-option {
    display: flex;
    align-items: center;
    gap: var(--sp-3);
    padding: var(--pad) var(--sp-4);
    border-radius: var(--radius);
    border: 1px solid var(--line);
    cursor: pointer;
    transition: background var(--fast) var(--ease);
}
.org-option:hover { background: var(--surface-2); }
.org-option-icon { font-size: 1.5rem; }
.org-option-titel { font-weight: 600; font-size: var(--fs-sm); }
.org-option-text { font-size: var(--fs-sm); color: var(--muted); }
.org-formular { display: flex; flex-direction: column; gap: var(--sp-3); }
/* UXD-R28: Farbwaehler statt Freitext — es kann kein ungueltiger Wert entstehen. */
.org-farbwahl { display: flex; align-items: center; gap: var(--sp-3); }
.org-farbwahl-feld {
    inline-size: 48px;
    block-size: 32px;
    padding: 0;
    border: 1px solid var(--line);
    border-radius: var(--radius);
    background: var(--surface);
    cursor: pointer;
}
.org-farbwahl-wert { font-size: var(--fs-sm); color: var(--muted); }
</style>
