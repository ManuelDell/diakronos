<template>
    <div class="dk-pub-page">
        <div class="dk-pub-card" style="max-width: 400px;">

            <!-- Fehler-Seite -->
            <div v-if="linkFehler" class="dk-pub-center">
                <div class="dk-pub-icon-large">🔒</div>
                <h1 class="dk-pub-title">Zugang nicht möglich</h1>
                <p class="dk-pub-muted">{{ linkFehler }}</p>
            </div>

            <!-- Erfolgseite -->
            <div v-else-if="success" class="dk-pub-center">
                <div class="dk-pub-icon-large">✅</div>
                <h1 class="dk-pub-title">Anmeldung übermittelt!</h1>
                <p class="dk-pub-muted">Danke! Deine Anmeldung wurde übermittelt.</p>
            </div>

            <!-- Formular -->
            <template v-else>
                <h1 class="dk-pub-title">Gast-Anmeldung</h1>
                <p class="dk-pub-muted" style="margin-bottom:24px">
                    Schnell und einfach – nur dein Name und eine kurze Datenschutzzustimmung.
                </p>

                <ErrorMessage v-if="fehler" :message="fehler" class="mb-4" />

                <form @submit.prevent="absenden" class="dk-pub-form" novalidate>
                    <FormControl type="text" label="Vorname *" v-model="form.vorname" autocomplete="given-name" />
                    <FormControl type="text" label="Nachname *" v-model="form.nachname" autocomplete="family-name" />

                    <!-- DSGVO / Einwilligung: Text kommt vom Server
                         (window.__diakronos.texte). Genau dieser Wortlaut wird
                         beim Absenden als Beleg gespeichert (N9b/H-1).
                         Reiner Text, kein HTML. -->
                    <div class="dk-pub-dsgvo">
                        <p v-if="willkommenstext" class="dk-pub-willkommen">{{ willkommenstext }}</p>
                        <p class="dk-pub-dsgvo-text" style="font-size:12px">{{ texte.einwilligung }}</p>
                        <label class="dk-pub-check">
                            <input type="checkbox" v-model="form.dsgvo" class="dk-pub-checkbox" />
                            <span class="dk-pub-dsgvo-label" style="font-size:12px">Ich stimme zu. *</span>
                        </label>
                    </div>

                    <Button type="submit" variant="solid" class="dk-pub-submit" :loading="loading">
                        Anmelden
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
// N9b (H-1, M-1): Einwilligungstext und Willkommenstext kommen vom Server.
// Es ist GENAU der Wortlaut, den submit_gast als Beleg speichert.
const texte      = window.__diakronos?.texte || {}
const willkommenstext = (window.__diakronos?.willkommenstext || '').trim()

const success = ref(false)
const loading = ref(false)
const fehler  = ref('')

const form = reactive({ vorname: '', nachname: '', dsgvo: false })

async function absenden() {
    fehler.value = ''
    if (!form.vorname.trim() || !form.nachname.trim()) {
        fehler.value = 'Vor- und Nachname sind Pflichtfelder.'
        return
    }
    if (!form.dsgvo) {
        fehler.value = 'Bitte stimme der Datenschutzzustimmung zu.'
        return
    }

    loading.value = true
    try {
        const csrf = document.querySelector('meta[name="csrf-token"]')?.content
                   || window.csrf_token || ''
        const res = await fetch('/api/method/diakronos.diakonos.api.registrierung.submit_gast', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Frappe-CSRF-Token': csrf,
            },
            body: JSON.stringify({ token, vorname: form.vorname.trim(), nachname: form.nachname.trim(), dsgvo: form.dsgvo,
                // N12b (W2a): die Fassung, die der Person angezeigt wurde.
                // Ohne dieses Feld nimmt der Server den Rueckwaerts-Pfad und
                // belegt die AKTUELLE statt der angezeigten Fassung — der
                // Nachweis waere dann nicht mehr Art. 7 DSGVO (angezeigt =
                // bestaetigt). Wie auf der Registrierungsseite.
                dsgvo_fassung: texte.einwilligung_fassung ?? '' }),
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
/* Diakronos Public Page — gast lädt diakonos/index.css (tokens.css), daher
   stammen alle Farben/Raumwerte aus dem gemeinsamen Token-System. */

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
  font-size: 20px;
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

.dk-pub-dsgvo {
  background: var(--surface-2);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 14px;
  font-size: 13px;
}

.dk-pub-dsgvo-text {
  color: var(--muted);
  margin: 0 0 10px 0;
  line-height: 1.5;
  white-space: pre-line;
}

/* N9b: gepflegter Willkommenstext ueber dem Formular. */
.dk-pub-willkommen {
  color: var(--text);
  font-weight: 500;
  margin: 0 0 10px 0;
  line-height: 1.5;
  white-space: pre-line;
}

.dk-pub-dsgvo-label {
  font-weight: 500;
  color: var(--text);
}

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
