<template>
    <div class="dk-pub-page">
        <div class="dk-pub-card">

            <!-- Fehler-Seite (Link ungültig) -->
            <div v-if="linkFehler" class="dk-pub-center">
                <div class="dk-pub-icon-large">🔒</div>
                <h1 class="dk-pub-title">Zugang nicht möglich</h1>
                <p class="dk-pub-muted">{{ linkFehler }}</p>
            </div>

            <!-- Erfolgsseite -->
            <div v-else-if="success" class="dk-pub-center">
                <div class="dk-pub-icon-large">✅</div>
                <h1 class="dk-pub-title">Anmeldung übermittelt!</h1>
                <p class="dk-pub-muted">
                    Vielen Dank! Deine Anmeldung wurde übermittelt.
                    Der Mitgliederadministrator prüft und bestätigt sie.
                </p>
            </div>

            <!-- Formular -->
            <template v-else>
                <h1 class="dk-pub-title">{{ titel }}</h1>
                <p class="dk-pub-muted" style="margin-bottom:24px">{{ subtitel }}</p>

                <ErrorMessage v-if="fehler" :message="fehler" class="mb-4" />

                <form @submit.prevent="absenden" class="dk-pub-form" novalidate>
                    <div class="dk-pub-grid-2">
                        <FormControl type="text" label="Vorname *" v-model="form.vorname" autocomplete="given-name" />
                        <FormControl type="text" label="Nachname *" v-model="form.nachname" autocomplete="family-name" />
                    </div>
                    <FormControl type="email" label="E-Mail (empfohlen)" v-model="form.email" autocomplete="email" />
                    <div class="dk-pub-grid-2">
                        <FormControl type="tel" label="Telefon (optional)" v-model="form.telefon" autocomplete="tel" />
                        <FormControl type="date" label="Geburtstag (optional)" v-model="form.geburtstag" />
                    </div>

                    <!-- Custom Felder -->
                    <div v-for="feld in felder" :key="feld.label" class="dk-pub-field-group">
                        <label class="dk-pub-label">
                            {{ feld.label }}<span v-if="feld.pflichtfeld" class="dk-pub-required"> *</span>
                        </label>

                        <!-- Text / Zahl / Datum -->
                        <input v-if="['Text','Zahl','Datum'].includes(feld.feldtyp)"
                               :type="feldtypToInput(feld.feldtyp)"
                               v-model="antworten[feld.label]"
                               :required="!!feld.pflichtfeld"
                               class="dk-pub-input" />

                        <!-- Ja-Nein -->
                        <label v-else-if="feld.feldtyp === 'Ja-Nein'" class="dk-pub-check">
                            <input type="checkbox" v-model="antworten[feld.label]"
                                   :required="!!feld.pflichtfeld"
                                   class="dk-pub-checkbox" />
                            <span>Ja</span>
                        </label>

                        <!-- Auswahl -->
                        <select v-else-if="feld.feldtyp === 'Auswahl'" v-model="antworten[feld.label]"
                                :required="!!feld.pflichtfeld"
                                class="dk-pub-input dk-pub-select">
                            <option value="">Bitte wählen…</option>
                            <option v-for="opt in feld.optionen.split('\n').filter(Boolean)" :key="opt" :value="opt">{{ opt }}</option>
                        </select>
                    </div>

                    <!-- Kinder-Sektion -->
                    <div v-if="mitKinder" class="dk-pub-kinder-box">
                        <h3 class="dk-pub-kinder-title">Kinder anmelden</h3>
                        <div v-for="(kind, idx) in kinder" :key="idx" class="dk-pub-kinder-row">
                            <div class="dk-pub-kinder-col-4">
                                <input v-model="kind.vorname" placeholder="Vorname *"
                                       class="dk-pub-input" />
                            </div>
                            <div class="dk-pub-kinder-col-4">
                                <input v-model="kind.nachname" placeholder="Nachname"
                                       class="dk-pub-input" />
                            </div>
                            <div class="dk-pub-kinder-col-3">
                                <input v-model="kind.geburtstag" type="date" placeholder="Geburtstag"
                                       class="dk-pub-input" />
                            </div>
                            <div class="dk-pub-kinder-col-1">
                                <button type="button" @click="kinder.splice(idx,1)"
                                        v-if="kinder.length > 1"
                                        class="dk-pub-remove-btn">×</button>
                            </div>
                        </div>
                        <button type="button" @click="kinder.push({vorname:'',nachname:'',geburtstag:''})"
                                class="dk-pub-add-btn">
                            + Kind hinzufügen
                        </button>
                    </div>

                    <!-- Dokument-Bestätigung -->
                    <div v-if="dokumente.length" class="dk-pub-dokumente">
                        <h3 class="dk-pub-dokumente-title">Dokumente</h3>
                        <div v-for="dok in dokumente" :key="dok.label" class="dk-pub-dokument-row">
                            <label class="dk-pub-check">
                                <input type="checkbox" v-model="dokBestaetigt[dok.label]"
                                       :required="!!dok.pflicht"
                                       class="dk-pub-checkbox" />
                                <span>
                                    <a v-if="dok.datei" :href="dok.datei" target="_blank" rel="noopener" class="dk-pub-dok-link">
                                        {{ dok.label }}<span v-if="dok.pflicht"> *</span>
                                    </a>
                                    <span v-else>{{ dok.label }}<span v-if="dok.pflicht"> *</span></span>
                                    gelesen und akzeptiert
                                </span>
                            </label>
                        </div>
                    </div>

                    <!-- DSGVO / Einwilligung: der Text kommt vom Server
                         (window.__diakronos.texte) und ist GENAU der Wortlaut,
                         den der Server beim Absenden als Beleg speichert
                         (N9b/H-1, Art. 7 DSGVO). Reiner Text, kein HTML. -->
                    <div class="dk-pub-dsgvo">
                        <p v-if="willkommenstext" class="dk-pub-willkommen">{{ willkommenstext }}</p>
                        <p class="dk-pub-dsgvo-text">{{ texte.einwilligung }}</p>
                        <label class="dk-pub-check">
                            <input type="checkbox" v-model="form.dsgvo" class="dk-pub-checkbox" />
                            <span class="dk-pub-dsgvo-label">Ich stimme der Verarbeitung meiner Daten gemäß obiger Erklärung zu. *</span>
                        </label>
                        <details v-if="texte.datenschutzerklaerung" class="dk-pub-details">
                            <summary>Datenschutzerklärung</summary>
                            <p class="dk-pub-dsgvo-text">{{ texte.datenschutzerklaerung }}</p>
                        </details>
                        <details v-if="texte.aufbewahrung" class="dk-pub-details">
                            <summary>Wie lange werden meine Daten gespeichert?</summary>
                            <p class="dk-pub-dsgvo-text">{{ texte.aufbewahrung }}</p>
                        </details>
                    </div>

                    <Button type="submit" variant="solid" class="dk-pub-submit" :loading="loading">
                        Anmeldung absenden
                    </Button>
                </form>
            </template>
        </div>
    </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { Button, FormControl, ErrorMessage } from 'frappe-ui'

const token      = window.__diakronos?.token || ''
const linkFehler = window.__diakronos?.linkFehler || ''
const felder     = window.__diakronos?.felder || []
const mitKinder  = window.__diakronos?.mitKinder || 0
const dokumente  = window.__diakronos?.dokumente || []
// N9b (H-1, M-1): die Einwilligungs-/Datenschutztexte kommen vom Server
// (window.__diakronos.texte, Quelle `gemeinde.wirksame_texte`) — reiner
// Text, NIE v-html. Es ist genau der Wortlaut, den der Server als Beleg
// speichert. Ist nichts gepflegt/veroeffentlicht, greifen die Server-
// Standardtexte; kommt das Objekt gar nicht an, zeigen wir nichts.
const texte      = window.__diakronos?.texte || {}
const willkommenstext = (window.__diakronos?.willkommenstext || '').trim()

const titel    = mitKinder ? 'Anmeldung' : 'Mitglied werden'
const subtitel = mitKinder
    ? 'Melde dich und deine Kinder an. Alle Daten werden sicher gespeichert.'
    : 'Registriere dich als Gemeindemitglied. Alle Daten werden sicher gespeichert.'

const success = ref(false)
const loading = ref(false)
const fehler  = ref('')

const form = reactive({
    vorname:    '',
    nachname:   '',
    email:      '',
    telefon:    '',
    geburtstag: '',
    dsgvo:      false,
})

const antworten = reactive({})
const kinder = ref([{ vorname: '', nachname: '', geburtstag: '' }])
const dokBestaetigt = reactive({})

function feldtypToInput(typ) {
    return { Text: 'text', Zahl: 'number', Datum: 'date' }[typ] || 'text'
}

async function absenden() {
    fehler.value = ''
    if (!form.vorname.trim() || !form.nachname.trim()) {
        fehler.value = 'Vor- und Nachname sind Pflichtfelder.'
        return
    }
    if (!form.dsgvo) {
        fehler.value = 'Bitte stimme der Datenschutzerklärung zu.'
        return
    }

    for (const f of felder) {
        if (f.pflichtfeld && !antworten[f.label]) {
            fehler.value = `Bitte fülle das Feld "${f.label}" aus.`
            return
        }
    }

    for (const dok of dokumente) {
        if (dok.pflicht && !dokBestaetigt[dok.label]) {
            fehler.value = `Bitte bestätige: "${dok.label}"`
            return
        }
    }

    loading.value = true
    try {
        const csrf = document.querySelector('meta[name="csrf-token"]')?.content
                   || window.csrf_token || ''
        const res = await fetch('/api/method/diakronos.diakonos.api.registrierung.submit_registrierung', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Frappe-CSRF-Token': csrf,
            },
            body: JSON.stringify({
                token,
                vorname:    form.vorname.trim(),
                nachname:   form.nachname.trim(),
                email:      form.email.trim(),
                telefon:    form.telefon.trim(),
                geburtstag: form.geburtstag || '',
                antworten: JSON.stringify(
                    Object.entries(antworten).map(([label, wert]) => ({ label, wert }))
                ),
                kinder: mitKinder ? JSON.stringify(
                    kinder.value.filter(k => k.vorname.trim())
                ) : '[]',
                // P0-4b: die Einwilligung wird jetzt serverseitig verlangt —
                // ohne dieses Feld entstuende kein gueltiger Nachweis.
                dsgvo: form.dsgvo,
                // N-1: die Fassung, die der Person angezeigt wurde. Wurde der
                // Text in der Zwischenzeit geaendert, lehnt der Server ab.
                dsgvo_fassung: texte.einwilligung_fassung ?? '',
            }),
        })
        const data = await res.json()
        if (!res.ok || data.exc) {
            fehler.value = parseServerError(data)
            return
        }
        success.value = true
    } catch {
        fehler.value = 'Verbindungsfehler. Bitte versuche es erneut.'
    } finally {
        loading.value = false
    }
}

function parseServerError(data) {
    if (!data) return 'Ein Fehler ist aufgetreten. Bitte versuche es erneut.'
    // UXD-R27: der Serverfehlertext steht in `message` (Compat-Schicht:
    // `_error_response` -> {"message": …}); die Frappe-Schreibweise
    // `_server_messages` wird weiter unterstuetzt (Altbestand).
    if (typeof data.message === 'string' && data.message.trim()) {
        return data.message
    }
    try {
        const msgs = JSON.parse(data._server_messages || '[]')
        if (msgs.length) return JSON.parse(msgs[0]).message
    } catch {}
    return 'Ein Fehler ist aufgetreten. Bitte versuche es erneut.'
}
</script>

<style>
/* Diakronos Public Page — Farben/Raumwerte kommen aus tokens.css (Import in
   main.js). Der frühere lokale :root-Block mit kopierten Token-WERTEN ist
   entfernt: tokens.css ist die einzige Quelle (Wächter-Test DS3). */

.dk-pub-page {
  min-height: 100vh;
  background: var(--bg);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  font-size: 14px;
  line-height: 1.5;
  color: var(--text);
  -webkit-font-smoothing: antialiased;
}

.dk-pub-card {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-md);
  width: 100%;
  max-width: 520px;
  padding: 40px;
}

@media (max-width: 640px) {
  .dk-pub-card { padding: 24px; }
  .dk-pub-page { padding: 16px; }
}

.dk-pub-center { text-align: center; }

.dk-pub-icon-large { font-size: 48px; margin-bottom: 16px; }

.dk-pub-title {
  font-size: 22px;
  font-weight: 600;
  color: var(--text);
  margin: 0 0 6px 0;
  letter-spacing: -0.01em;
}

.dk-pub-muted {
  font-size: 13px;
  color: var(--muted);
  margin: 0;
  line-height: 1.5;
}

.dk-pub-form { display: flex; flex-direction: column; gap: 14px; }

.dk-pub-grid-2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
@media (max-width: 480px) {
  .dk-pub-grid-2 { grid-template-columns: 1fr; }
}

.dk-pub-field-group { display: flex; flex-direction: column; gap: 6px; }

.dk-pub-label {
  font-size: 13px;
  font-weight: 500;
  color: var(--text);
}

.dk-pub-required { color: var(--err); }

.dk-pub-input {
  width: 100%;
  padding: 9px 12px;
  font-size: 14px;
  color: var(--text);
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  outline: none;
  transition: border-color 150ms var(--ease), box-shadow 150ms var(--ease);
  font-family: inherit;
}
.dk-pub-input:focus {
  border-color: var(--primary);
  box-shadow: 0 0 0 3px color-mix(in oklch, var(--primary) 12%, transparent);
}
.dk-pub-input::placeholder { color: var(--subtle); }

.dk-pub-select { appearance: auto; cursor: pointer; }

.dk-pub-check {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  font-size: 13px;
  color: var(--text);
}

.dk-pub-checkbox {
  width: 16px;
  height: 16px;
  accent-color: var(--primary);
  cursor: pointer;
  flex-shrink: 0;
}

.dk-pub-kinder-box {
  background: var(--surface-2);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.dk-pub-kinder-title { font-size: 13px; font-weight: 600; color: var(--text); margin: 0; }

.dk-pub-kinder-row {
  display: grid;
  grid-template-columns: 4fr 4fr 3fr 1fr;
  gap: 8px;
  align-items: end;
}
@media (max-width: 480px) {
  .dk-pub-kinder-row { grid-template-columns: 1fr 1fr; }
  .dk-pub-kinder-col-3, .dk-pub-kinder-col-1 { grid-column: span 1; }
}

.dk-pub-remove-btn {
  color: var(--err);
  font-size: 20px;
  font-weight: 700;
  background: none;
  border: none;
  cursor: pointer;
  padding: 0 4px;
  line-height: 1;
}
.dk-pub-remove-btn:hover { color: var(--dk-red-700); }

.dk-pub-add-btn {
  font-size: 13px;
  font-weight: 500;
  color: var(--primary);
  background: none;
  border: none;
  cursor: pointer;
  padding: 0;
  text-align: left;
}
.dk-pub-add-btn:hover { color: var(--primary-hover); text-decoration: underline; }

.dk-pub-dokumente {
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 16px;
  font-size: 13px;
}
.dk-pub-dokumente-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin: 0 0 10px;
}
.dk-pub-dokument-row { margin-bottom: 8px; }
.dk-pub-dok-link { color: var(--primary); text-decoration: underline; }

.dk-pub-dsgvo {
  background: var(--surface-2);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 16px;
  font-size: 13px;
}

.dk-pub-dsgvo-text { color: var(--muted); margin: 0 0 12px 0; line-height: 1.5; white-space: pre-line; }

.dk-pub-dsgvo-label { font-weight: 500; color: var(--text); }

/* N9b: der gepflegte Willkommenstext steht hervorgehoben ueber dem Formular. */
.dk-pub-willkommen {
  color: var(--text);
  font-weight: 500;
  margin: 0 0 12px 0;
  line-height: 1.5;
  white-space: pre-line;
}

/* N9b: Datenschutzerklaerung/Aufbewahrung als aufklappbare Textbloecke
   (reiner Text, kein HTML). */
.dk-pub-details { margin-top: 8px; }
.dk-pub-details summary {
  cursor: pointer;
  color: var(--primary);
  font-weight: 500;
  padding: 4px 0;
}
.dk-pub-details .dk-pub-dsgvo-text { margin: 8px 0 0 0; }

.dk-pub-submit {
  width: 100%;
  background: var(--primary) !important;
  border-color: var(--primary) !important;
}
.dk-pub-submit:hover {
  background: var(--primary-hover) !important;
  border-color: var(--primary-hover) !important;
}
</style>
