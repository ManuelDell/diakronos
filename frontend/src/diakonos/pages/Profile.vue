<template>
  <div class="dk-screen dk-screen-enter">

    <!-- Seitenkopf -->
    <DkPageHeader title="Mein Profil" />

    <div v-if="loading" class="prof-loading">
      <div class="prof-skelett-kreis" />
      <div class="prof-skelett-zeile" />
    </div>

    <div v-else-if="error" class="prof-fehler">
      <DkHint variant="err" role="alert">{{ error }}</DkHint>
      <p>Personen ohne Konto oder ohne zugeordneten Personeneintrag wenden sich für Auskunft, Einwilligungen und Löschung an die Gemeindeverwaltung.</p>
    </div>

    <div v-else class="prof-layout">

      <!-- ── Avatar-Karte ── -->
      <DkCard>
        <div class="prof-avatar-card">
          <div class="prof-avatar-wrap" @click="openCropModal">
            <div class="prof-avatar" :style="avatarStyle">
              <img v-if="profile.foto" :src="profile.foto" alt="Foto" />
              <span v-else>{{ initials }}</span>
            </div>
            <!-- OP-HANDY-22: Am Handy gibt es kein „Überfahren" — das
                 Kamera-Zeichen lag in einem Overlay, das nur bei Hover erschien,
                 und war deshalb unsichtbar. Der Hinweis ist jetzt IMMER zu
                 sehen (kleines Zeichen dauerhaft, Text darunter). -->
            <div class="prof-avatar-overlay">
              <svg class="dk-icon-lg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/><circle cx="12" cy="13" r="4"/></svg>
            </div>
          </div>
          <div class="prof-avatar-info">
            <div class="prof-avatar-name">{{ profile.vorname }} {{ profile.nachname }}</div>
            <div class="prof-avatar-email dk-text-muted">{{ profile.email }}</div>
            <div class="prof-avatar-aktionen">
              <DkButton variant="secondary" size="sm" @click="openCropModal">
                {{ profile.foto ? 'Foto ändern' : 'Foto auswählen' }}
              </DkButton>
              <DkButton v-if="profile.foto" variant="ghost" size="sm" @click="fotoEntfernen">
                Foto entfernen
              </DkButton>
            </div>
          </div>
        </div>
      </DkCard>

      <!-- ── Persönliche Daten ── -->
      <DkCard title="Persönliche Daten">
        <template #actions>
          <DkButton v-if="!editingData" variant="ghost" size="sm" @click="startEdit">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
            Bearbeiten
          </DkButton>
          <div v-else class="prof-aktionen">
            <DkButton variant="ghost" size="sm" @click="cancelEdit">Abbrechen</DkButton>
            <DkButton variant="primary" size="sm" :loading="saving" @click="saveData">Speichern</DkButton>
          </div>
        </template>

        <div class="prof-fields" :class="{ 'is-editing': editingData }">
          <div class="prof-field-row">
            <div class="prof-field">
              <label>Vorname</label>
              <input v-if="editingData" v-model="form.vorname" class="dk-ui-eingabe" />
              <span v-else>{{ profile.vorname || '—' }}</span>
            </div>
            <div class="prof-field">
              <label>Nachname</label>
              <input v-if="editingData" v-model="form.nachname" class="dk-ui-eingabe" />
              <span v-else>{{ profile.nachname || '—' }}</span>
            </div>
          </div>
          <div class="prof-field-row">
            <div class="prof-field">
              <label>Geburtstag</label>
              <input v-if="editingData" v-model="form.geburtstag" type="date" class="dk-ui-eingabe" />
              <span v-else>{{ profile.geburtstag ? formatDate(profile.geburtstag) : '—' }}</span>
            </div>
            <div class="prof-field">
              <label>Geschlecht</label>
              <DkSelect v-if="editingData" v-model="form.geschlecht" :options="geschlechtOptionen" />
              <span v-else>{{ profile.geschlecht || '—' }}</span>
            </div>
          </div>
          <div class="prof-field-row">
            <div class="prof-field">
              <label>Telefon</label>
              <input v-if="editingData" v-model="form.telefonnummer" type="tel" class="dk-ui-eingabe" />
              <span v-else>{{ profile.telefonnummer || '—' }}</span>
            </div>
            <div class="prof-field">
              <label>Familienstand</label>
              <DkSelect v-if="editingData" v-model="form.familienstand" :options="familienstandOptionen" />
              <span v-else>{{ profile.familienstand || '—' }}</span>
            </div>
          </div>
          <div class="prof-field-row">
            <div class="prof-field prof-field-wide">
              <label>Straße &amp; Nummer</label>
              <div v-if="editingData" class="prof-strasse">
                <input v-model="form.strasse" class="dk-ui-eingabe" placeholder="Straße" />
                <input v-model="form.nummer" class="dk-ui-eingabe prof-nr" placeholder="Nr." />
              </div>
              <span v-else>{{ [profile.strasse, profile.nummer].filter(Boolean).join(' ') || '—' }}</span>
            </div>
          </div>
          <div class="prof-field-row">
            <div class="prof-field">
              <label>PLZ</label>
              <input v-if="editingData" v-model="form.postleitzahl" class="dk-ui-eingabe" />
              <span v-else>{{ profile.postleitzahl || '—' }}</span>
            </div>
            <div class="prof-field">
              <label>Wohnort</label>
              <input v-if="editingData" v-model="form.wohnort" class="dk-ui-eingabe" />
              <span v-else>{{ profile.wohnort || '—' }}</span>
            </div>
          </div>
          <div class="prof-field-row">
            <div class="prof-field prof-field-wide">
              <label>E-Mail</label>
              <span class="prof-hinweis">
                {{ profile.email }}
                <!-- OP-ADMIN-16: Der Link „Passwort ändern ↗“ führte auf eine
                     rohe 404-Seite. Passwörter setzt in dieser Installation die
                     Gemeindeleitung — hier steht deshalb nur der Hinweis. -->
                <span class="prof-klein">Passwort vergessen? Melde dich bei der Gemeindeleitung.</span>
              </span>
            </div>
          </div>
        </div>
      </DkCard>

      <!-- ── Adressbuch-Sichtbarkeit ── -->
      <DkCard title="Adressbuch-Sichtbarkeit">
        <template #actions>
          <span class="prof-klein">Was andere eingeloggte Mitglieder sehen dürfen</span>
        </template>
        <div class="prof-toggles">
          <!-- OP-HANDY-21: Das Kästchen war nur 16 px groß — am Handy kaum zu
               treffen. Die ganze Zeile ist jetzt die Schalterfläche
               (`@click`), das Kästchen selbst bleibt das fokussierbare,
               vorlesbare Element. Kein verschachteltes <label>, weil
               DkCheckbox bereits eines mitbringt. -->
          <div
            v-for="s in sichtbarkeitZeilen"
            :key="s.key"
            class="prof-toggle-row prof-toggle-row--klickbar"
            @click="sichtbarkeit[s.key] = !sichtbarkeit[s.key]; saveSichtbarkeit()"
          >
            <div class="prof-toggle-info">
              <span class="prof-toggle-label">{{ s.label }}</span>
              <span class="prof-toggle-desc dk-text-muted">{{ s.beschreibung }}</span>
            </div>
            <!-- Klick auf das Kästchen darf nicht doppelt umschalten. -->
            <span @click.stop>
              <DkCheckbox :model-value="sichtbarkeit[s.key]" @update:model-value="sichtbarkeit[s.key] = $event; saveSichtbarkeit()" />
            </span>
          </div>
        </div>
      </DkCard>

      <!-- ── Datenschutz (DSGVO) ── -->
      <DkCard title="Meine Daten &amp; Datenschutz">
        <h3>Meine Einwilligungen</h3>
        <p class="prof-klein">Den gespeicherten Nachweis findest du in deiner Datenauskunft. Für Fragen zur Datenverarbeitung oder ihren Widerruf wende dich an die Gemeindeverwaltung.</p>
        <div v-if="profile.datenschutz_einwilligung" class="prof-dsgvo-status prof-dsgvo-status--ok">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><polyline points="9 12 11 14 15 10"/></svg>
          <div>
            <div class="prof-dsgvo-titel">Einwilligung erteilt</div>
            <div class="prof-klein">{{ profile.datenschutz_datum ? `am ${formatDate(profile.datenschutz_datum)}` : '' }}</div>
          </div>
        </div>
        <div v-else class="prof-dsgvo-status prof-dsgvo-status--warn">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
          <div>
            <div class="prof-dsgvo-titel">Keine Einwilligung</div>
            <div class="prof-klein">Du hast noch keine DSGVO-Einwilligung erteilt.</div>
          </div>
        </div>

        <!-- Einwilligungen -->
        <div v-for="e in einwilligungen" :key="e.key" class="prof-consent-row">
          <div class="prof-consent-info">
            <div class="prof-consent-label">{{ e.label }}</div>
            <div class="prof-consent-desc dk-text-muted">
              {{ profile[e.key] ? ('Erteilt am ' + formatDate(e.datumFeld ? profile[e.datumFeld] : null)) : 'Nicht erteilt' }}
            </div>
          </div>
          <DkButton
            size="sm"
            :variant="profile[e.key] ? 'ghost' : 'primary'"
            :disabled="savingConsent"
            @click="toggleEinwilligung(e.kurz, !profile[e.key])"
          >{{ profile[e.key] ? 'Widerrufen' : 'Erteilen' }}</DkButton>
        </div>

        <div class="prof-dsgvo-actions">
          <h3>Auskunft</h3>
          <p>Was ist über mich gespeichert? Hier kannst du deine zugeordneten Daten und Einwilligungsnachweise ansehen und als Datei speichern.</p>
          <DkButton variant="secondary" :loading="loadingAuskunft" @click="ladeAuskunft">Meine Daten ansehen / herunterladen</DkButton>
          <p class="prof-klein">Personen ohne Konto wenden sich für Auskunft, Einwilligungen oder Löschung an die Gemeindeverwaltung. Sie kann den Wunsch im Reiter Datenschutz bearbeiten.</p>
        </div>
      </DkCard>

      <!-- ── DSGVO-2b: Löschung auf Antrag ── -->
      <LoeschantragKarte
        v-if="profile.name"
        :antrag="loeschantrag"
        :laedt="!antragGeladen"
        :laeuft="deleting || zurueckziehenLaeuft"
        :fehler="datenschutzFehler"
        :dialog-fehler="dialogFehler"
        @beantragen="executeDelete"
        @zurueckziehen="antragZurueckziehen"
        @neu-laden="ladeAntragsstand"
      />

      <!-- ── BF1-L: Konto / Abmelden ── -->
      <DkCard title="Konto">
        <div class="prof-konto">
          <p class="prof-klein prof-konto-text">
            Angemeldet als <strong>{{ profile.email || 'Nutzer' }}</strong>.
          </p>
          <DkButton variant="secondary" size="sm" @click="abmeldenMitMeldung">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
            Abmelden
          </DkButton>
        </div>
      </DkCard>

    </div>

    <!-- ── Crop-Dialog ── -->
    <DkDialog v-model="showCrop" title="Profilbild ändern">
      <div class="prof-crop-area">
        <Cropper
          v-if="cropSrc"
          ref="cropperRef"
          :src="cropSrc"
          :stencil-props="{ aspectRatio: 1 }"
          stencil-component="circle-stencil"
          class="prof-cropper"
        />
        <div v-else class="prof-crop-upload" @click="triggerFileInput" @dragover.prevent @drop.prevent="onFileDrop">
          <input ref="fileInput" type="file" accept="image/*" style="display:none" @change="onFileSelect" />
          <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
          <p>Bild hier ablegen oder klicken zum Auswählen</p>
        </div>
      </div>
      <template #footer>
        <DkButton v-if="cropSrc" variant="ghost" size="sm" @click="cropSrc = null">Anderes Bild</DkButton>
        <DkButton variant="ghost" size="sm" @click="showCrop = false">Abbrechen</DkButton>
        <DkButton v-if="cropSrc" variant="primary" size="sm" :loading="uploadingPhoto" @click="cropAndUpload">Speichern</DkButton>
      </template>
    </DkDialog>

    <DkDialog v-model="showAuskunft" title="Meine gespeicherten Daten">
      <p>Diese Auskunft enthält deine zugeordneten Daten. Dateien sind als Verweise aufgeführt; Nennungen ohne technische Zuordnung prüft die Gemeinde gesondert.</p>
      <pre class="prof-auskunft" tabindex="0">{{ JSON.stringify(auskunft, null, 2) }}</pre>
      <template #footer>
        <DkButton variant="ghost" @click="showAuskunft = false">Schließen</DkButton>
        <DkButton variant="primary" @click="downloadAuskunft">Als Datei herunterladen</DkButton>
      </template>
    </DkDialog>

  </div>
</template>

<script setup>
/**
 * Profile — eigenes Profil im Design-System „A · Ruhig & Klar“.
 * Reiner Darstellungsumbau: Kopf, Karten, Dialoge, Felder und Kästchen
 * kommen aus components/ui; Farben nur aus tokens.css.
 */
import { ref, computed, reactive, onMounted } from 'vue'
import { Cropper } from 'vue-advanced-cropper'
import 'vue-advanced-cropper/dist/style.css'
import DkPageHeader from '../components/ui/DkPageHeader.vue'
import DkButton from '../components/ui/DkButton.vue'
import DkCard from '../components/ui/DkCard.vue'
import DkDialog from '../components/ui/DkDialog.vue'
import DkSelect from '../components/ui/DkSelect.vue'
import DkCheckbox from '../components/ui/DkCheckbox.vue'
import DkHint from '../components/ui/DkHint.vue'
import LoeschantragKarte from '../components/mitglieder/LoeschantragKarte.vue'
import { useAbmelden } from '../composables/useAbmelden.js'
import { useFormularSchutz } from '../composables/useFormularSchutz.js'
import { useVerlassenSchutz } from '../composables/useVerlassenSchutz.js'
import { showToast } from '../composables/useToast.js'
import { apiCall } from '../composables/useApi.js'
import { apiAntwortPruefen } from '../composables/useApi.js'
import {
  antragsstandLaden, loeschungBeantragen, antragZurueckziehen as antragZurueckziehenApi,
  antragFehlerText,
} from '../composables/useLoeschantrag.js'

const { abmelden } = useAbmelden()

/** W3: Fehler beim Abmelden melden, statt still auf /login zu wechseln. */
async function abmeldenMitMeldung() {
  const ergebnis = await abmelden()
  if (ergebnis && ergebnis.ok === false) {
    showToast(ergebnis.fehler || 'Abmelden fehlgeschlagen.', 'error')
  }
}

/** Zentraler Zugang zur Profil-API über den gemeinsamen Sitzungspfad (OP-UI-1). */
function profilApi(method, body = {}) {
  return apiCall('diakronos.diakonos.api.' + method, body)
}

// State
const loading = ref(true)
const error = ref(null)
const saving = ref(false)
const editingData = ref(false)
const uploadingPhoto = ref(false)
const deleting = ref(false)
const zurueckziehenLaeuft = ref(false)
const loadingAuskunft = ref(false), showAuskunft = ref(false), auskunft = ref(null)
const loeschantrag = ref(null), antragGeladen = ref(false)
const datenschutzFehler = ref(''), dialogFehler = ref('')
const savingConsent = ref(false)
const showCrop = ref(false)
const cropSrc = ref(null)
const cropperRef = ref(null)
const fileInput = ref(null)

const profile = ref({})
const form = reactive({})
const sichtbarkeit = reactive({ email: true, telefonnummer: true, adresse: false, geburtstag: false })

// UXD-R29: Rückfrage beim Wegnavigieren mit ungespeicherten Profil-Eingaben.
// Solange das Formular zu ist, gibt es nichts zu verlieren (lesen() -> null).
const datenSchutz = useFormularSchutz(
    () => (editingData.value ? form : null),
    () => saving.value,
)
useVerlassenSchutz(datenSchutz)

const COLORS = [
  'var(--dk-navy-400)', 'var(--dk-navy-500)', 'var(--dk-navy-300)',
  'var(--dk-gold-500)', 'var(--dk-gold-700)',
]
const avatarStyle = computed(() => {
  if (profile.value.foto) return {}
  const idx = (profile.value.vorname || 'U').charCodeAt(0) % COLORS.length
  return { background: COLORS[idx], color: 'var(--primary-ink)' }
})

/* Bausteine beschicken */
const geschlechtOptionen = [
  { value: '', label: '—' },
  { value: 'Männlich', label: 'Männlich' },
  { value: 'Weiblich', label: 'Weiblich' },
  { value: 'Divers', label: 'Divers' },
]
const familienstandOptionen = [
  { value: '', label: '—' },
  { value: 'Ledig', label: 'Ledig' },
  { value: 'Verheiratet', label: 'Verheiratet' },
  { value: 'Verwitwet', label: 'Verwitwet' },
  { value: 'Geschieden', label: 'Geschieden' },
]
const sichtbarkeitZeilen = computed(() => [
  { key: 'email', label: 'E-Mail-Adresse', beschreibung: profile.value.email || 'Nicht angegeben' },
  { key: 'telefonnummer', label: 'Telefonnummer', beschreibung: profile.value.telefonnummer || 'Nicht angegeben' },
  { key: 'adresse', label: 'Adresse', beschreibung: fullAddress.value || 'Nicht angegeben' },
  { key: 'geburtstag', label: 'Geburtstag', beschreibung: profile.value.geburtstag ? formatDate(profile.value.geburtstag) : 'Nicht angegeben' },
])
const einwilligungen = [
  { key: 'foto_einwilligung', datumFeld: 'foto_datum', kurz: 'foto', label: 'Foto-Einwilligung' },
  { key: 'werbeeinwilligung', datumFeld: 'werbung_datum', kurz: 'werbung', label: 'Werbeeinwilligung' },
]
const initials = computed(() => {
  const v = profile.value.vorname?.[0] || ''
  const n = profile.value.nachname?.[0] || ''
  return (v + n).toUpperCase() || 'U'
})
const fullAddress = computed(() => {
  const p = profile.value
  const street = [p.strasse, p.nummer].filter(Boolean).join(' ')
  const city = [p.postleitzahl, p.wohnort].filter(Boolean).join(' ')
  return [street, city].filter(Boolean).join(', ')
})

function formatDate(d) {
  if (!d) return ''
  const dt = new Date(d.replace(' ', 'T'))
  return dt.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric' })
}

async function loadProfile() {
  loading.value = true
  error.value = null
  try {
    const data = await profilApi('profile.get_my_profile')
    Object.assign(profile.value, data)
    Object.assign(sichtbarkeit, data.adressbuch_sichtbarkeit || {})
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

function startEdit() {
  Object.assign(form, {
    vorname: profile.value.vorname,
    nachname: profile.value.nachname,
    telefonnummer: profile.value.telefonnummer,
    postleitzahl: profile.value.postleitzahl,
    wohnort: profile.value.wohnort,
    strasse: profile.value.strasse,
    nummer: profile.value.nummer,
    geburtstag: profile.value.geburtstag,
    geschlecht: profile.value.geschlecht,
    familienstand: profile.value.familienstand,
  })
  editingData.value = true
  // UXD-R29: Grundstand erst nach dem Befüllen merken.
  datenSchutz.merken()
}

function cancelEdit() {
  editingData.value = false
}

async function saveData() {
  saving.value = true
  try {
    await profilApi('profile.update_my_profile', { ...form })
    Object.assign(profile.value, form)
    editingData.value = false
    showToast('Dein Profil wurde gespeichert.', 'success')
  } catch (e) {
    showToast(e?.message || 'Deine Änderungen konnten nicht gespeichert werden.', 'error')
  } finally {
    saving.value = false
  }
}

async function saveSichtbarkeit() {
  try {
    await profilApi('profile.update_adressbuch_sichtbarkeit', { settings: { ...sichtbarkeit } })
  } catch (e) {
    showToast(e?.message || 'Die Sichtbarkeit konnte nicht gespeichert werden.', 'error')
  }
}

function openCropModal() {
  cropSrc.value = null
  showCrop.value = true
}
function triggerFileInput() { fileInput.value?.click() }
function onFileSelect(e) {
  const file = e.target.files[0]
  if (file) readFile(file)
}
function onFileDrop(e) {
  const file = e.dataTransfer.files[0]
  if (file) readFile(file)
}
function readFile(file) {
  const reader = new FileReader()
  reader.onload = (e) => { cropSrc.value = e.target.result }
  reader.readAsDataURL(file)
}

async function cropAndUpload() {
  if (!cropperRef.value) return
  const { canvas } = cropperRef.value.getResult()
  if (!canvas) return
  uploadingPhoto.value = true
  try {
    const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg', 0.85))
    const fd = new FormData()
    fd.append('file', blob, 'profilbild.jpg')
    fd.append('is_private', '0')
    fd.append('folder', 'Home/Attachments')
    const csrf = document.querySelector('meta[name="csrf-token"]')?.content || ''
    const res = await fetch('/api/method/upload_file', {
      method: 'POST',
      headers: { 'X-Frappe-CSRF-Token': csrf },
      body: fd,
    })
    const json = await apiAntwortPruefen(res)
    const url = json.message?.file_url
    if (!url) throw new Error('Upload fehlgeschlagen')
    await profilApi('profile.update_profile_picture', { file_url: url })
    profile.value.foto = url
    showCrop.value = false
    cropSrc.value = null
  } catch (e) {
    showToast(e?.message || 'Das hat nicht geklappt. Bitte später noch einmal versuchen.', 'error')
  } finally {
    uploadingPhoto.value = false
  }
}

/**
 * OP-HANDY-22: Profilfoto entfernen. Ein leerer `file_url` löscht den Verweis
 * (serverseitig `profile.update_profile_picture`). Rückmeldung wie beim
 * Speichern — vorher passierte am Handy sichtbar nichts.
 */
async function fotoEntfernen() {
  try {
    await profilApi('profile.update_profile_picture', { file_url: '' })
    profile.value.foto = ''
    showToast('Das Profilfoto wurde entfernt.', 'success')
  } catch (e) {
    showToast(e?.message || 'Das Foto konnte nicht entfernt werden.', 'error')
  }
}

async function ladeAntragsstand() {
  antragGeladen.value = false
  datenschutzFehler.value = ''
  try {
    loeschantrag.value = await antragsstandLaden()
    antragGeladen.value = true
  } catch (e) { datenschutzFehler.value = antragFehlerText(e, 'Der Stand deines Antrags konnte nicht geladen werden.') }
}
/**
 * DSGVO-2b: Der Antrag kommt aus dem Bestätigungsdialog der Karte
 * (Kontrollkästchen + abgetipptes Wort). `bestaetigt: true` setzt die API
 * selbst (`useLoeschantrag.loeschungBeantragen`).
 */
async function executeDelete() {
  if (deleting.value) return
  deleting.value = true
  dialogFehler.value = ''
  try {
    loeschantrag.value = await loeschungBeantragen()
    showToast('Löschantrag gestellt. Die Gemeindeverwaltung prüft ihn.', 'success')
  } catch (e) {
    // Der Dialog bleibt offen (die Karte schließt ihn nur bei einem gesetzten
    // Antrag) — die Person liest die Meldung und kann es erneut versuchen.
    dialogFehler.value = antragFehlerText(e, 'Der Löschantrag konnte nicht gestellt werden.')
  } finally {
    deleting.value = false
  }
}
/** Offenen Antrag zurückziehen; danach ist ein neuer Antrag möglich. */
async function antragZurueckziehen() {
  if (zurueckziehenLaeuft.value) return
  zurueckziehenLaeuft.value = true
  datenschutzFehler.value = ''
  dialogFehler.value = ''
  try {
    loeschantrag.value = await antragZurueckziehenApi()
    showToast('Dein Löschantrag wurde zurückgezogen.', 'success')
  } catch (e) {
    datenschutzFehler.value = antragFehlerText(e, 'Der Antrag konnte nicht zurückgezogen werden.')
  } finally {
    zurueckziehenLaeuft.value = false
  }
}
async function ladeAuskunft() {
  if (loadingAuskunft.value) return
  loadingAuskunft.value = true
  datenschutzFehler.value = ''
  try {
    auskunft.value = await profilApi('datenschutz.meine_auskunft')
    showAuskunft.value = true
  } catch (e) { datenschutzFehler.value = e?.message || 'Auskunft konnte nicht geladen werden.' }
  finally { loadingAuskunft.value = false }
}
function downloadAuskunft() {
  if (!auskunft.value) return
  const url = URL.createObjectURL(new Blob([JSON.stringify(auskunft.value, null, 2)], { type: 'application/json' }))
  const a = document.createElement('a')
  a.href = url
  a.download = 'meine-datenauskunft.json'
  a.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

async function toggleEinwilligung(typ, erteilt) {
  savingConsent.value = true
  try {
    await profilApi(`profile.update_einwilligung`, { typ, erteilt: erteilt ? 1 : 0 })
    await loadProfile()
  } catch (e) {
    showToast(e?.message || 'Die Einwilligung konnte nicht gespeichert werden.', 'error')
  } finally {
    savingConsent.value = false
  }
}

onMounted(async () => {
  await loadProfile()
  if (!error.value) await ladeAntragsstand()
})
</script>

<style scoped>
.prof-loading { display: flex; align-items: center; gap: var(--sp-4); padding: var(--sp-8) 0; }
.prof-skelett-kreis { width: 60px; height: 60px; border-radius: 50%; background: var(--surface-2); animation: prof-puls 1.5s infinite; }
.prof-skelett-zeile { flex: 1; height: 16px; width: 40%; border-radius: var(--radius-sm); background: var(--surface-2); animation: prof-puls 1.5s infinite; }
@keyframes prof-puls { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
.prof-fehler { margin-top: var(--sp-6); }
.prof-layout { display: flex; flex-direction: column; gap: var(--sp-4); padding-bottom: 80px; }
.prof-aktionen { display: flex; gap: var(--sp-2); }
.prof-klein { font-size: var(--fs-sm); color: var(--muted); }

/* Avatar-Karte */
.prof-avatar-card { display: flex; align-items: center; gap: var(--sp-5); }
.prof-avatar-wrap {
  position: relative; width: 72px; height: 72px;
  border-radius: 50%; cursor: pointer; flex-shrink: 0;
  overflow: hidden;
}
.prof-avatar {
  width: 100%; height: 100%; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: var(--fs-h1); font-weight: 700;
}
.prof-avatar img { width: 100%; height: 100%; object-fit: cover; }
.prof-avatar-overlay {
  position: absolute; inset: 0;
  background: color-mix(in oklch, var(--dk-navy-900) 55%, transparent);
  display: flex; align-items: center; justify-content: center;
  /* OP-HANDY-22: vorher `opacity: 0` + Hover — am Handy unsichtbar. Jetzt
     dauerhaft sichtbar, beim Überfahren etwas kräftiger. */
  opacity: 1; transition: opacity var(--fast); color: var(--dk-warm-0); border-radius: 50%;
}
.prof-avatar-wrap:hover .prof-avatar-overlay,
.prof-avatar-wrap:focus-visible .prof-avatar-overlay { opacity: 1; background: color-mix(in oklch, var(--dk-navy-900) 70%, transparent); }
/* OP-HANDY-22: sichtbare, beschriftete Knöpfe für das Profilfoto. */
.prof-avatar-aktionen { display: flex; flex-wrap: wrap; gap: var(--sp-2); margin-top: var(--sp-2); }
.prof-avatar-name { font-weight: 600; font-size: var(--fs-h3); }
.prof-avatar-email { font-size: var(--fs-sm); }

/* Felder */
.prof-fields { display: flex; flex-direction: column; gap: var(--sp-3); }
.prof-field-row { display: grid; grid-template-columns: 1fr 1fr; gap: var(--sp-3); }
.prof-field-wide { grid-column: 1 / -1; }
.prof-field { display: flex; flex-direction: column; gap: var(--sp-1); }
.prof-field label { font-size: var(--fs-xs); font-weight: 600; color: var(--muted); text-transform: uppercase; letter-spacing: 0.5px; }
.prof-field span { font-size: var(--fs); padding: 6px 0; }
/* UXD-R9: siehe MitgliedDetail — `.prof-strasse .dk-ui-eingabe{flex:1}`
   überstimmte `.prof-nr{flex:0 0 70px}`, und ohne `min-width:0` schrumpfte
   kein Feld unter seine Inhaltsbreite. Am Handy lief das Formular über den
   Kartenrand. */
.prof-strasse { display: flex; gap: var(--sp-2); }
.prof-strasse .prof-nr,
.prof-strasse .dk-ui-eingabe.prof-nr { flex: 0 0 70px; }
.prof-strasse .dk-ui-eingabe { min-width: 0; }
.prof-hinweis { font-size: var(--fs-sm); color: var(--muted); }
.prof-link { margin-left: var(--sp-2); font-size: var(--fs-sm); color: var(--primary); text-decoration: none; }
.prof-link:hover { text-decoration: underline; }

/* Umschalter */
.prof-toggles { display: flex; flex-direction: column; }
.prof-toggle-row {
  display: flex; align-items: center; justify-content: space-between;
  padding: var(--sp-3) 0;
  border-bottom: 1px solid var(--line);
}
/* OP-HANDY-21: Die ganze Zeile schaltet um; Mindesthöhe wie ein Fingertipp. */
.prof-toggle-row--klickbar { cursor: pointer; min-height: var(--row-h); }
.prof-toggle-row--klickbar:hover { background: var(--surface-hover); }
.prof-toggle-row:last-child { border-bottom: none; }
.prof-toggle-info { display: flex; flex-direction: column; gap: 2px; }
.prof-toggle-label { font-size: var(--fs); font-weight: 500; }
.prof-toggle-desc { font-size: var(--fs-sm); }

/* DSGVO */
.prof-auskunft { max-height: 50vh; overflow: auto; white-space: pre-wrap; overflow-wrap: anywhere; font-size: var(--fs-sm); }
.prof-dsgvo-actions h3 { margin-top: var(--sp-4); }
.prof-dsgvo-actions p { margin-block: var(--sp-3); }
.prof-dsgvo-status {
  display: flex; align-items: flex-start; gap: var(--sp-3);
  padding: var(--pad);
  border-radius: var(--radius);
  margin-bottom: var(--sp-4);
}
.prof-dsgvo-status--ok { background: var(--ok-soft); color: var(--ok); }
.prof-dsgvo-status--warn { background: var(--warn-soft); color: var(--warn); }
.prof-dsgvo-titel { font-weight: 600; }
.prof-dsgvo-actions { padding-top: var(--sp-3); }

/* BF1-L: Konto-Karte mit Abmelden. */
.prof-konto {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-3);
}
.prof-konto-text { margin: 0; }

.prof-consent-row {
  display: flex; align-items: center; justify-content: space-between;
  padding: var(--sp-3) 0;
  border-top: 1px solid var(--line);
  gap: var(--sp-3);
}
.prof-consent-info { display: flex; flex-direction: column; gap: 2px; flex: 1; }
.prof-consent-label { font-size: var(--fs); font-weight: 500; }
.prof-consent-desc { font-size: var(--fs-sm); }

/* Dialoginhalte */
.prof-crop-area { min-height: 300px; display: flex; align-items: center; justify-content: center; }
.prof-cropper { width: 100%; max-height: 340px; }
.prof-crop-upload {
  border: 2px dashed var(--line); border-radius: var(--radius);
  padding: 40px; text-align: center; cursor: pointer; width: 100%;
  color: var(--muted);
  display: flex; flex-direction: column; align-items: center; gap: var(--sp-3);
}
.prof-crop-upload:hover { border-color: var(--primary); }
.prof-crop-upload p { margin: 0; font-size: var(--fs); }

@media (max-width: 600px) {
  /* UXD-R9: `minmax(0,1fr)` statt `1fr` — sonst bleibt die Spur so breit wie
     das breiteste Kind und schiebt das Formular über den Kartenrand. */
  .prof-field-row { grid-template-columns: minmax(0, 1fr); }
  .prof-avatar-card { flex-direction: column; text-align: center; }
}
</style>
