<template>
    <div class="dk-screen dk-screen-enter">
        <!-- Seitenkopf -->
        <DkPageHeader
            :title="fullName"
            :krumen="[{ text: 'Mitglieder', href: '#/mitglieder' }, { text: fullName }]"
            :badges="[{ text: mitglied?.status || 'Unbekannt', variant: statusVariante }]"
        >
            <template #actions>
                <!-- OP-ADMIN-12: Der frühere Vorschau-Knopf ist hier ENTFERNT.
                     Er tat in Wahrheit, was er versprach, NICHT:
                     das Frontend schickt `__impersonated_as` mit, das Backend
                     ignoriert es überall (das Modul `impersonation` ist im
                     Standalone-Backend nicht portiert, siehe
                     `permissions._get_effective_user`, das bewusst
                     `session.user` zurückgibt). Die Vorschau zeigte damit die
                     ADMINISTRATOR-Sicht (Kachel „Zu moderierende Termine“,
                     8 Kalender mit Verwalten-Knopf, „30 von 30+ Personen“) —
                     wer damit Rechte prüfte, schloss falsch. Ein Ausblenden
                     ist ehrlicher als ein Banner: der Knopf kommt zurück,
                     sobald die Impersonation im Backend existiert. -->
                <DkButton v-if="canEdit && !isEditing" variant="secondary" @click="startEdit">
                    Bearbeiten
                </DkButton>
                <!-- AUSTRITT A1/A4: Austritt und Reaktivieren sitzen hier bei
                     „Bearbeiten“ — dieselbe Stelle wie bisher „Ausschließen“.
                     Welcher der beiden Knoepfe erscheint, entscheidet der
                     Zustand der Person; beide Wege sind umkehrbar. Das
                     endgültige Löschen auf Antrag (DSGVO) ist eine eigene
                     Karte und steht bewusst NICHT hier. -->
                <DkButton
                    v-if="canEdit && !isEditing && austrittLage.art === 'austritt'"
                    variant="primary"
                    @click="austrittDialog = true"
                >Reaktivieren</DkButton>
                <DkButton
                    v-else-if="canEdit && !isEditing && austrittLage.art === ''"
                    variant="danger"
                    @click="austrittDialog = true"
                >Austritt / Deaktivieren</DkButton>
                <template v-else-if="isEditing">
                    <DkButton variant="secondary" @click="cancelEdit">Abbrechen</DkButton>
                    <DkButton variant="primary" :loading="isSaving" @click="saveEdit">Speichern</DkButton>
                </template>
            </template>
        </DkPageHeader>

        <!-- Reiter -->
        <div class="md-tabs">
            <DkTabs v-model="activeTab" :options="tabs.map(t => ({ value: t.key, label: t.label }))" aria-label="Bereiche" />
        </div>

        <!-- Laden -->
        <div v-if="loading" class="md-zustand">Lade Mitglied…</div>

        <!-- Fehler -->
        <DkHint v-else-if="error" variant="err">{{ error }}</DkHint>

        <!-- AUSTRITT A3/A4: „ausgetreten seit …“ — nur für Administratoren,
             die den Grund auch sehen dürfen. Der Server liefert beides nur an
             Berechtigte; hier wird nichts erfunden.
             Die Kette unten (`v-else-if` der Reiter-Karten) haengt an diesem
             `v-if`/`v-else-if` — die Hinweise stehen deshalb in einem
             eigenen Block, nicht dazwischen. -->
        <template v-if="!loading && !error && austrittLage.art === 'austritt'">
            <DkHint variant="info" class="md-austritt">
                Ausgetreten seit {{ datumDeutsch(austrittLage.seit) }}<template v-if="austrittLage.grund"> — {{ austrittLage.grund }}</template>.
                Die Person erscheint in Plänen nur noch gekürzt; das Konto ist deaktiviert.
            </DkHint>
        </template>
        <!-- AUSTRITT-d (NB3): Der Ausschluss-Hinweis UND der Aufhebe-Weg sind
             eine Verwaltungssache — Nicht-Admins sehen ihn nicht (sie bekommen
             vom Server ohnehin keine Begruendung und koennen nichts aendern). -->
        <template v-else-if="!loading && !error && canEdit && austrittLage.art === 'ausschluss'">
            <DkHint variant="warn" class="md-austritt">
                Ausgeschlossen seit {{ datumDeutsch(austrittLage.seit) }}. Zum Aufheben bitte den Status im Profil ändern.
            </DkHint>
        </template>

        <!-- Reiter: Details -->
        <DkCard v-if="!loading && !error && activeTab === 'details'" title="Persönliche Daten">
            <!-- Ansicht -->
            <div v-if="!isEditing">
                <div v-for="z in detailZeilen" :key="z.label" class="md-zeile">
                    <span class="md-label">{{ z.label }}</span>
                    <span class="md-wert">
                        <template v-if="z.mehrzeilig">
                            {{ z.adresse1 }}<br v-if="z.adresse1" />{{ z.adresse2 }}
                        </template>
                        <template v-else>{{ z.wert }}</template>
                    </span>
                </div>
            </div>

            <!-- Bearbeiten -->
            <div v-else class="edit-form">
                <div class="edit-grid">
                    <DkField label="Vorname" required :error="formFehler.vorname">
                        <input v-model="editForm.vorname" type="text" class="dk-ui-eingabe" maxlength="140" />
                    </DkField>
                    <DkField label="Nachname" required :error="formFehler.nachname">
                        <input v-model="editForm.nachname" type="text" class="dk-ui-eingabe" maxlength="140" />
                    </DkField>
                    <DkField label="E-Mail" :error="formFehler.email">
                        <input v-model="editForm.email" type="email" class="dk-ui-eingabe" maxlength="140" />
                    </DkField>
                    <DkField label="Telefon">
                        <input v-model="editForm.telefon" type="tel" class="dk-ui-eingabe" maxlength="140" />
                    </DkField>
                    <DkField label="Geburtstag">
                        <input v-model="editForm.geburtstag" type="date" class="dk-ui-eingabe" />
                    </DkField>
                    <DkField label="Status">
                        <DkSelect v-model="editForm.status" :options="statusOptionen" />
                    </DkField>
                    <DkField label="Geschlecht">
                        <DkSelect v-model="editForm.geschlecht" :options="geschlechtOptionen" />
                    </DkField>
                    <DkField label="Familienstand">
                        <DkSelect v-model="editForm.familienstand" :options="familienstandOptionen" />
                    </DkField>
                    <DkField label="Straße &amp; Hausnummer" class="edit-field-full">
                        <div class="md-strasse">
                            <input v-model="editForm.strasse" type="text" class="dk-ui-eingabe" placeholder="Straße" maxlength="140" />
                            <input v-model="editForm.hausnummer" type="text" class="dk-ui-eingabe md-nr" placeholder="Nr." maxlength="140" />
                        </div>
                    </DkField>
                    <DkField label="PLZ">
                        <input v-model="editForm.plz" type="text" class="dk-ui-eingabe" maxlength="140" />
                    </DkField>
                    <DkField label="Ort">
                        <input v-model="editForm.ort" type="text" class="dk-ui-eingabe" maxlength="140" />
                    </DkField>
                </div>
                <p class="md-muted md-ausschluss-hinweis">
                    Eine Person wird nie gelöscht. „Austritt / Deaktivieren“
                    ist umkehrbar: das Konto ruht, alte Pläne zeigen die
                    Person gekürzt („Vorname N.“), und „Reaktivieren“ gibt den
                    vorherigen Status zurück und stellt den Kontozustand von
                    vor dem Austritt wieder her — war das Konto vorher
                    gesperrt, bleibt es gesperrt (eine Sperre hebst du unter
                    „Zugang“ auf). „Ausschließen“ ist der harte Fall
                    (Fehlverhalten): es setzt den Status <em>Passiver Gast</em>
                    mit Vermerk und Datum, die Person bleibt in den Listen
                    voll sichtbar, und aufgehoben wird es über den Status im
                    Profil. Die endgültige Löschung auf Antrag
                    (DSGVO) folgt als eigener Weg.
                </p>
            </div>
        </DkCard>

        <!-- UXD-R26: Der frühere Reiter „Dienste“ ist ENTFERNT. Er zeigte nur
             einen Platzhaltertext — einen Hinweis, der eine Funktion
             behauptete, die es nicht gibt. Wer Dienst-Übersichten
             sucht, findet sie unter „Dienste“ im Plan-Bereich
             (#/planrahmen/meine-dienste bzw. im Dienstplan). -->

        <!-- Reiter: Gruppen (UXD-R26) — echte Daten statt Platzhaltertext.
             Die Zuordnung kommt aus `get_gruppen_for_mitglied` (derselbe
             Endpunkt, den auch die Gruppenseite benutzt). -->
        <DkCard v-else-if="activeTab === 'gruppen' && !loading && !error" title="Gruppen">
            <p v-if="gruppenLaedt" class="md-muted">Gruppen werden geladen …</p>
            <DkHint v-else-if="gruppenFehler" variant="err">{{ gruppenFehler }}</DkHint>
            <p v-else-if="gruppen.length === 0" class="md-muted">
                Diese Person ist in keiner Gruppe eingetragen.
            </p>
            <div v-else class="md-liste">
                <div v-for="g in gruppen" :key="g.gruppe" class="md-beziehung">
                    <a v-if="g.gruppe" class="md-beziehung-name" :href="'#/gruppe/' + encodeURIComponent(g.gruppe)">
                        {{ g.gruppenname || g.gruppe }}
                    </a>
                    <span v-else class="md-beziehung-name">{{ g.gruppenname || '—' }}</span>
                    <DkBadge :variant="g.quelle === 'gruppe' ? 'neutral' : 'info'">
                        {{ g.quelle === 'gruppe' ? (g.rolle || 'Mitglied') : 'über Obergruppe' }}
                    </DkBadge>
                </div>
            </div>
        </DkCard>

        <!-- Reiter: Beziehungen -->
        <DkCard v-else-if="activeTab === 'beziehungen' && !loading && !error" title="Beziehungen">
            <p v-if="!mitglied?.beziehungen || mitglied.beziehungen.length === 0" class="md-muted">
                Keine Beziehungen eingetragen.
            </p>
            <div v-else class="md-liste">
                <div v-for="b in mitglied.beziehungen" :key="b.name" class="md-beziehung">
                    <DkBadge variant="neutral">{{ b.beziehungstyp }}</DkBadge>
                    <span class="md-beziehung-name">{{ b.beziehung_zu_name || b.beziehung_zu }}</span>
                </div>
            </div>
        </DkCard>

        <!-- Reiter: DSGVO -->
        <DkCard v-else-if="activeTab === 'dsgvo' && !loading && !error" title="DSGVO & Einwilligungen">
            <div class="md-liste">
                <div v-for="e in einwilligungen" :key="e.label" class="md-beziehung">
                    <div>
                        <p class="md-einwilligung-titel">{{ e.label }}</p>
                        <p class="md-muted">{{ e.wert ? formatDate(e.datum) : e.leerText }}</p>
                    </div>
                    <DkBadge :variant="e.wert ? 'ok' : 'err'">{{ e.wert ? 'Ja' : 'Nein' }}</DkBadge>
                </div>
                <DkButton
                    v-if="dsgvo.datenschutz || dsgvo.foto || dsgvo.werbung"
                    variant="danger"
                    @click="widerrufEinwilligung"
                >Einwilligungen widerrufen</DkButton>
            </div>
        </DkCard>

        <!-- Reiter: Zugang (P1-8, OP-ADMIN-2) — nur für Administratoren -->
        <ZugangKarte
            v-else-if="activeTab === 'zugang' && canEdit && !loading && !error"
            :mitglied-id="mitgliedId"
            :email="mitglied?.email || ''"
            :oidc-aktiv="oidcAktiv"
        />

        <!-- AUSTRITT (A1/A4): ein Dialog fuer beide Richtungen.
             Keine native Rueckfrage des Browsers — Begruendung und Datum
             werden im Dialog erfasst. -->
        <AustrittDialog
            v-model="austrittDialog"
            :art="austrittLage.art === 'austritt' ? 'reaktivieren' : 'austritt'"
            :name="fullName"
            :zurueck-status="austrittLage.vorherigerStatus || 'Mitglied'"
            :laeuft="austrittLaeuft"
            @austritt="austrittBestaetigen"
            @reaktivieren="reaktivierenBestaetigen"
        />

        <!-- UXD-R26: Der Reiter „Historie“ ist ENTFERNT. Er versprach ein
             Audit-Log, das es an dieser Stelle nicht gibt („Audit-Log wird
             hier angezeigt“). Das Audit-Log der Anwendung ist eine eigene
             Verwaltungsansicht; ein Reiter, der nichts zeigt, ist ein
             Versprechen ohne Deckung. -->
    </div>
</template>

<script setup>
/**
 * MitgliedDetail — Einzelansicht im Design-System „A · Ruhig & Klar“.
 * Reiner Darstellungsumbau: Kopf, Reiter, Karten, Kennzeichen und Felder
 * kommen aus components/ui; Farben nur aus tokens.css.
 */
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useSession } from '../composables/useSession.js'
import { getRouteParam } from '../router.js'
import { apiCall, AuditConfirmationRequired } from '../composables/useApi.js'
import { useAuditConfirm } from '../composables/useAuditConfirm.js'
import { showToast } from '../composables/useToast.js'
import { useFormularSchutz } from '../composables/useFormularSchutz.js'
import { useVerlassenSchutz } from '../composables/useVerlassenSchutz.js'
import { bestaetigen } from '../composables/useBestaetigen.js'
import { lage as austrittLageAus, datumDeutsch, austrittErfassen, reaktivieren } from '../composables/useAustritt.js'
import AustrittDialog from '../components/austritt/AustrittDialog.vue'
import DkPageHeader from '../components/ui/DkPageHeader.vue'
import DkButton from '../components/ui/DkButton.vue'
import DkBadge from '../components/ui/DkBadge.vue'
import DkCard from '../components/ui/DkCard.vue'
import DkTabs from '../components/ui/DkTabs.vue'
import DkField from '../components/ui/DkField.vue'
import DkSelect from '../components/ui/DkSelect.vue'
import DkHint from '../components/ui/DkHint.vue'
import ZugangKarte from '../components/ZugangKarte.vue'

const { isAdmin } = useSession()
const { openConfirm, isSubmitting } = useAuditConfirm()

// P1-8: die Mitglieds-ID aus der Adresse — auch fuer die Zugang-Karte.
const mitgliedId = computed(() => getRouteParam('id', 'MitgliedDetail') || '')
// Ob Authentik aktiv ist, kommt aus dem Boot-Kontext (der Server entscheidet).
const oidcAktiv = computed(() => !!window.__DIakonosBOOT?.oidc_aktiv)

const mitglied = ref(null)
const loading = ref(true)
const error = ref(null)
const isSaving = ref(false)
/** AUSTRITT: Dialog offen (Austritt ODER Reaktivieren — ein Dialog, zwei Faelle). */
const austrittDialog = ref(false)
const austrittLaeuft = ref(false)
/** Lage der Person: Austritt, Ausschluss oder nichts (kommt vom Server). */
const austrittLage = computed(() => austrittLageAus(mitglied.value?.austritt))
const canEdit = computed(() => !error.value && mitglied.value && isAdmin.value)
const isEditing = ref(false)
const activeTab = ref('details')

/* UXD-R26: Beim Öffnen des Gruppen-Reiters die Zuordnung laden (einmalig).
   Ein `watch` statt „immer laden“: die Detailseite soll nicht bei jedem
   Aufruf eine zweite Anfrage stellen, die kaum jemand braucht. */
watch(activeTab, (neu) => {
    if (neu === 'gruppen') ladeGruppen()
})

const tabs = computed(() => {
    const liste = [
        { key: 'details', label: 'Details' },
        { key: 'gruppen', label: 'Gruppen' },
        { key: 'beziehungen', label: 'Beziehungen' },
        { key: 'dsgvo', label: 'DSGVO' },
        // P1-8 (OP-ADMIN-2): Zugang nur fuer Administratoren sichtbar.
        ...(canEdit.value ? [{ key: 'zugang', label: 'Zugang' }] : []),
    ]
    return liste
})

const editForm = reactive({
    vorname: '',
    nachname: '',
    email: '',
    telefon: '',
    geburtstag: '',
    status: '',
    strasse: '',
    hausnummer: '',
    plz: '',
    ort: '',
    geschlecht: '',
    familienstand: '',
})

/** UXD-R15/R24: Feldfehler vor dem Senden; Status zur Auswahl. */
const formFehler = reactive({ vorname: '', nachname: '', email: '' })
const statusOptionen = [
    { value: 'Mitglied', label: 'Mitglied' },
    { value: 'Gast', label: 'Gast' },
    { value: 'Passives Mitglied', label: 'Passives Mitglied' },
    { value: 'Passiver Gast', label: 'Passiver Gast' },
]

const dsgvo = reactive({
    datenschutz: false,
    datenschutz_datum: null,
    foto: false,
    foto_datum: null,
    werbung: false,
    werbung_datum: null,
})

const fullName = computed(() => {
    const m = mitglied.value
    if (!m) return 'Unbekannt'
    const v = (m.vorname ?? '').toString().trim()
    const n = (m.nachname ?? '').toString().trim()
    if (v || n) return `${v} ${n}`.trim()
    if (m.full_name) return m.full_name
    if (m.name) return m.name
    if (m.email) return m.email
    return 'Unbekannt'
})

const initials = computed(() => {
    const m = mitglied.value
    if (!m) return '?'
    const v = (m.vorname ?? '').toString().trim()[0] || ''
    const n = (m.nachname ?? '').toString().trim()[0] || ''
    return (v + n).toUpperCase() || '?'
})

function formatDate(date) {
    if (!date) return null
    try {
        return new Date(date).toLocaleDateString('de-DE')
    } catch {
        return date
    }
}

/* Bausteine beschicken */
const geschlechtOptionen = [
    { value: '', label: '– keine Angabe –' },
    { value: 'Männlich', label: 'Männlich' },
    { value: 'Weiblich', label: 'Weiblich' },
    { value: 'Divers', label: 'Divers' },
]
const familienstandOptionen = [
    { value: '', label: '– keine Angabe –' },
    { value: 'Ledig', label: 'Ledig' },
    { value: 'Verheiratet', label: 'Verheiratet' },
    { value: 'Verwitwet', label: 'Verwitwet' },
    { value: 'Geschieden', label: 'Geschieden' },
]

/** Mitgliedsstatus → Kennzeichen-Variante. */
const statusVariante = computed(() => {
    const s = mitglied.value?.status
    if (s === 'Aktiv') return 'ok'
    if (s === 'Inaktiv') return 'err'
    if (s === 'Pausiert') return 'warn'
    return 'neutral'
})

/** Zeilen der Reiter „Details“ (Ansicht). */
const detailZeilen = computed(() => {
    const m = mitglied.value || {}
    const strasse = [m.straße, m.nummer].filter(Boolean).join(' ')
    const ort = [m.postleitzahl, m.wohnort].filter(Boolean).join(' ')
    return [
        { label: 'Vorname', wert: m.vorname || '–' },
        { label: 'Nachname', wert: m.nachname || '–' },
        { label: 'E-Mail', wert: m.email || '–' },
        { label: 'Telefon', wert: m.telefonnummer || '–' },
        { label: 'Geburtstag', wert: formatDate(m.geburtstag) || '–' },
        { label: 'Geschlecht', wert: m.geschlecht || '–' },
        { label: 'Familienstand', wert: m.familienstand || '–' },
        { label: 'Adresse', mehrzeilig: true, adresse1: strasse || (ort ? '' : '–'), adresse2: ort },
        { label: 'Eintrittsdatum', wert: formatDate(m.eintrittsdatum) || '–' },
        { label: 'Letzte Anmeldung', wert: formatDate(m.letzte_anmeldung) || '–' },
    ]
})

/** Zeilen der Reiter „DSGVO“. */
const einwilligungen = computed(() => [
    { label: 'Datenschutzerklärung akzeptiert', wert: dsgvo.datenschutz, datum: dsgvo.datenschutz_datum, leerText: 'Nicht akzeptiert' },
    { label: 'Foto-Einwilligung', wert: dsgvo.foto, datum: dsgvo.foto_datum, leerText: 'Nicht erteilt' },
    { label: 'Werbeeinwilligung', wert: dsgvo.werbung, datum: dsgvo.werbung_datum, leerText: 'Nicht erteilt' },
])

/* UXD-R26: Gruppen erst laden, wenn der Reiter wirklich geöffnet wird — die
   Detailseite soll nicht bei jedem Aufruf eine zweite Anfrage stellen. Die
   Herkunft wird auf „gruppe“ oder „obergruppe“ abgebildet, damit die Anzeige
   den Unterschied macht, den der Server liefert (`source: ancestor_path`). */
const gruppen = ref([])
const gruppenLaedt = ref(false)
const gruppenFehler = ref('')
let gruppenGeladen = false

async function ladeGruppen() {
    if (gruppenGeladen || gruppenLaedt.value) return
    const id = mitgliedId.value
    if (!id) return
    gruppenLaedt.value = true
    gruppenFehler.value = ''
    try {
        const antwort = await apiCall('diakronos.diakonos.api.mitglieder.get_gruppen_for_mitglied', { mitglied_id: id })
        const daten = Array.isArray(antwort?.data) ? antwort.data : (Array.isArray(antwort) ? antwort : [])
        gruppen.value = daten.map(g => ({
            ...g,
            quelle: g.source === 'ancestor_path' ? 'obergruppe' : 'gruppe',
        }))
        gruppenGeladen = true
    } catch (e) {
        gruppenFehler.value = e?.message || 'Die Gruppen konnten nicht geladen werden.'
    } finally {
        gruppenLaedt.value = false
    }
}

function _fillEditForm(payload) {
    Object.assign(editForm, {
        vorname: payload.vorname || '',
        nachname: payload.nachname || '',
        email: payload.email || '',
        telefon: payload.telefonnummer || '',
        geburtstag: payload.geburtstag || '',
        status: payload.status || '',
        strasse: payload.straße || '',
        hausnummer: payload.nummer || '',
        plz: payload.postleitzahl || '',
        ort: payload.wohnort || '',
        geschlecht: payload.geschlecht || '',
        familienstand: payload.familienstand || '',
    })
    Object.assign(formFehler, { vorname: '', nachname: '', email: '' })
}

/** UXD-R24: Pflichtfelder + E-Mail-Format vor dem Senden pruefen. */
function _pruefeFormular() {
    let ok = true
    Object.assign(formFehler, { vorname: '', nachname: '', email: '' })
    if (!(editForm.vorname || '').trim()) { formFehler.vorname = 'Vorname ist ein Pflichtfeld.'; ok = false }
    if (!(editForm.nachname || '').trim()) { formFehler.nachname = 'Nachname ist ein Pflichtfeld.'; ok = false }
    const mail = (editForm.email || '').trim()
    if (mail && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(mail)) {
        formFehler.email = 'Bitte eine gültige E-Mail-Adresse angeben.'
        ok = false
    }
    return ok
}

/** UXD-R6: Das Geburtsdatum wird immer mitgesendet — ein leeres Feld loescht
 *  den Wert (der Server wandelt '' in NULL).
 *
 *  Befund 9 (P1-9b): Ein LEERER Status wurde als `''` mitgesendet. Beim
 *  Nicht-Admin löste das einen PermissionError aus, beim Admin setzte der
 *  Server still „Gast“ — eine stille Datenänderung. Ein leerer Status wird
 *  deshalb gar nicht erst gesendet. */
function _formDaten() {
    const daten = {
        vorname: (editForm.vorname || '').trim(),
        nachname: (editForm.nachname || '').trim(),
        email: (editForm.email || '').trim(),
        telefon: editForm.telefon,
        geburtstag: editForm.geburtstag || '',
        strasse: editForm.strasse,
        hausnummer: editForm.hausnummer,
        plz: editForm.plz,
        ort: editForm.ort,
        geschlecht: editForm.geschlecht,
        familienstand: editForm.familienstand,
    }
    const status = (editForm.status || '').trim()
    if (status) daten.status = status
    return daten
}

async function loadMitglied() {
    const id = mitgliedId.value
    // Die alte Lazy-Seite kann beim Wechsel kurz neu gemountet werden.
    // Ohne eigenen Routenscope gibt es hier nichts zu laden.
    if (!id) return
    loading.value = true
    error.value = null
    try {
        const response = await apiCall('diakronos.diakonos.api.mitglieder.get_mitglied_detail', { mitglied_id: id })
        const payload = response?.data ?? response

        if (!payload || typeof payload !== 'object') {
            throw new Error('Ungültige Daten vom Server')
        }

        mitglied.value = payload
        _fillEditForm(payload)

        if (payload.dsgvo) {
            Object.assign(dsgvo, payload.dsgvo)
        }
    } catch (e) {
        console.error('[MitgliedDetail] load error:', e)
        error.value = e.message || 'Mitglied konnte nicht geladen werden'
    } finally {
        loading.value = false
    }
}

function startEdit() {
    _fillEditForm(mitglied.value || {})
    isEditing.value = true
    // UXD-R29: Grundstand erst jetzt merken — erst ab hier zaehlt „geaendert“.
    editSchutz.merken()
}

function cancelEdit() {
    isEditing.value = false
}

async function saveEdit() {
    if (isSaving.value) return
    // UXD-R24: Pflichtfelder/Format vor dem Senden pruefen; nichts senden,
    // wenn die Eingabe ungueltig ist.
    if (!_pruefeFormular()) {
        showToast('Bitte die markierten Felder prüfen', 'error')
        return
    }
    isSaving.value = true
    const idempotencyKey = generateIdempotencyKey()
    try {
        const id = getRouteParam('id')
        await apiCall('diakronos.diakonos.api.mitglieder.update_mitglied', {
            mitglied_id: id,
            data: JSON.stringify(_formDaten()),
        })
        showToast('Mitglied gespeichert', 'success')
        isEditing.value = false
        await loadMitglied()
    } catch (err) {
        if (err instanceof AuditConfirmationRequired) {
            const reason = await openConfirm(err.policy)
            if (!reason) {
                showToast('Abgebrochen', 'info')
                return
            }
            const id = getRouteParam('id')
            isSubmitting.value = true
            try {
                await apiCall('diakronos.diakonos.api.mitglieder.update_mitglied', {
                    mitglied_id: id,
                    data: JSON.stringify(_formDaten()),
                    __audit_confirmation: JSON.stringify({
                        policy_name: err.policy.policy_name,
                        reason: reason,
                        idempotency_key: idempotencyKey,
                    }),
                })
                showToast('Mitglied gespeichert', 'success')
                isEditing.value = false
                await loadMitglied()
            } finally {
                isSubmitting.value = false
            }
        } else {
            console.error('[MitgliedDetail] save error:', err)
            showToast(err.message || 'Speichern fehlgeschlagen', 'error')
        }
    } finally {
        isSaving.value = false
    }
}

function generateIdempotencyKey() {
    if (typeof crypto !== 'undefined' && crypto.randomUUID) {
        return crypto.randomUUID()
    }
    return Date.now().toString(36) + '-' + Math.random().toString(36).slice(2)
}

/* ── AUSTRITT (A1/A4) ─────────────────────────────────────────────────────
   Zwei Wege, beide umkehrbar und beide nur fuer Administratoren. Der Server
   entscheidet ueber das Recht; hier wird nur gesendet und die Antwort
   angezeigt. Das endgueltige Loeschen (DSGVO) ist eine eigene Karte. */

async function austrittBestaetigen({ begruendung, datum }) {
    if (austrittLaeuft.value) return
    austrittLaeuft.value = true
    try {
        const antwort = await austrittErfassen(mitgliedId.value || getRouteParam('id'), begruendung, datum)
        austrittDialog.value = false
        showToast(
            antwort?.konto_deaktiviert
                ? 'Austritt erfasst: Das Konto ist deaktiviert und alle Sitzungen wurden beendet.'
                : 'Austritt erfasst.',
            'success',
        )
        await loadMitglied()
    } catch (err) {
        console.error('[MitgliedDetail] Austritt fehlgeschlagen:', err)
        showToast(err?.message || 'Der Austritt konnte nicht erfasst werden.', 'error')
    } finally {
        austrittLaeuft.value = false
    }
}

async function reaktivierenBestaetigen() {
    if (austrittLaeuft.value) return
    austrittLaeuft.value = true
    try {
        const antwort = await reaktivieren(mitgliedId.value || getRouteParam('id'))
        austrittDialog.value = false
        showToast(`Person ist wieder aktiv (Status „${antwort?.status || 'Mitglied'}“).`, 'success')
        await loadMitglied()
    } catch (err) {
        console.error('[MitgliedDetail] Reaktivieren fehlgeschlagen:', err)
        showToast(err?.message || 'Die Person konnte nicht reaktiviert werden.', 'error')
    } finally {
        austrittLaeuft.value = false
    }
}

async function widerrufEinwilligung() {
    if (!await bestaetigen({ titel: 'Alle Einwilligungen widerrufen?', text: 'Alle gespeicherten Einwilligungen dieser Person werden widerrufen. Das Mitglied wird nicht gelöscht.', aktion: 'Alle widerrufen', gefahr: true })) return
    const idempotencyKey = generateIdempotencyKey()
    try {
        const id = getRouteParam('id')
        await apiCall('diakronos.diakonos.api.mitglieder.widerruf_einwilligung', { mitglied_id: id })
        showToast('Einwilligungen widerrufen', 'success')
        await loadMitglied()
    } catch (err) {
        if (err instanceof AuditConfirmationRequired) {
            const reason = await openConfirm(err.policy)
            if (!reason) {
                showToast('Abgebrochen', 'info')
                return
            }
            const id = getRouteParam('id')
            isSubmitting.value = true
            try {
                await apiCall('diakronos.diakonos.api.mitglieder.widerruf_einwilligung', {
                    mitglied_id: id,
                    __audit_confirmation: JSON.stringify({
                        policy_name: err.policy.policy_name,
                        reason: reason,
                        idempotency_key: idempotencyKey,
                    }),
                })
                showToast('Einwilligungen widerrufen', 'success')
                await loadMitglied()
            } finally {
                isSubmitting.value = false
            }
        } else {
            console.error('[MitgliedDetail] widerruf error:', err)
            showToast(err.message || 'Widerruf fehlgeschlagen', 'error')
        }
    }
}

// UXD-R29: fragt beim Wegnavigieren (Zurück-Taste, Seitenleiste) nach, wenn
// das Bearbeiten-Formular offen ist und ungespeicherte Eingaben enthält.
// `isEditing` in `lesen()` ist Absicht: ohne offenes Formular gibt es nichts
// zu verlieren, also auch keine Rückfrage.
const editSchutz = useFormularSchutz(
    () => (isEditing.value ? editForm : null),
    () => isSaving.value || isSubmitting.value,
)
useVerlassenSchutz(editSchutz)

onMounted(loadMitglied)
</script>

<style scoped>
.md-tabs { margin-bottom: var(--sp-6); }
.md-zustand { padding: var(--sp-8); text-align: center; color: var(--muted); }
.md-muted { color: var(--muted); margin: 0; }

.md-zeile {
    display: flex;
    justify-content: space-between;
    gap: var(--sp-4);
    padding: var(--sp-3) 0;
    border-bottom: 1px solid var(--line);
}
.md-zeile:last-child { border-bottom: none; }
.md-label { font-weight: 500; color: var(--muted); }
.md-wert { color: var(--text); text-align: right; }

/* UXD-R9: Am Handy liefen die Bearbeiten-Formulare von Mitglied und Profil
   über den Rand; „Nr.“ war abgeschnitten. Ursache: `.md-strasse .dk-ui-eingabe
   {flex:1}` überstimmte `.md-nr{flex:0 0 70px}`, und ein Flex-Kind ohne
   `min-width:0` kann nicht unter seine Inhaltsbreite schrumpfen. Beides wird
   hier korrigiert; die spezifischere Regel gewinnt wieder gegen `flex:1`. */
.md-strasse { display: flex; gap: var(--sp-2); }
.md-strasse .md-nr,
.md-strasse .dk-ui-eingabe.md-nr { flex: 0 0 70px; }
.md-strasse .dk-ui-eingabe { min-width: 0; }

.edit-form { padding-top: var(--sp-1); }
.edit-grid { display: grid; grid-template-columns: 1fr 1fr; gap: var(--sp-4); }
.edit-field-full { grid-column: 1 / -1; }
/* UXD-R9: eine Spalte am Handy; `minmax(0,1fr)` laesst die Felder
   mitschrumpfen statt die Karte zu sprengen. */
@media (max-width: 600px) {
    .edit-grid { grid-template-columns: minmax(0, 1fr); }
}

.md-liste { display: flex; flex-direction: column; gap: var(--sp-3); }
.md-beziehung {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--sp-3);
    padding: var(--sp-3);
    background: var(--surface-2);
    border-radius: var(--radius);
}
.md-beziehung-name { font-weight: 500; color: var(--text); }
.md-einwilligung-titel { margin: 0; font-weight: 500; color: var(--text); }
.md-ausschluss-hinweis { margin-top: var(--sp-3); font-size: var(--fs-sm); }
</style>
