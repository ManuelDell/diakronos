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

                    <!-- DSGVO -->
                    <div class="dk-pub-dsgvo">
                        <p class="dk-pub-dsgvo-text" style="font-size:12px">
                            Dein Name wird zum Zweck der Anwesenheitsverwaltung gespeichert
                            (Art.&nbsp;6 Abs.&nbsp;1 lit.&nbsp;a DSGVO). Keine Weitergabe an Dritte.
                        </p>
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
            body: JSON.stringify({ token, vorname: form.vorname.trim(), nachname: form.nachname.trim() }),
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
    try {
        const msgs = JSON.parse(data._server_messages || '[]')
        if (msgs.length) return JSON.parse(msgs[0]).message
    } catch {}
    return 'Ein Fehler ist aufgetreten. Bitte versuche es erneut.'
}
</script>

<style>
/* Diakronos Public Page Design System */
:root {
  --dk-bg:           #fafaf8;
  --dk-surface:      #ffffff;
  --dk-surface-2:    #f7f7f4;
  --dk-border:       #e6e6e0;
  --dk-border-strong:#d4d4cc;
  --dk-text:         #15182a;
  --dk-text-muted:   #5a617a;
  --dk-text-subtle:  #8a90a5;
  --dk-brand-500:    #1c2850;
  --dk-brand-800:    #00051f;
  --dk-accent:       #d4a24c;
  --dk-success:      #16a34a;
  --dk-danger:       #dc2626;
  --dk-shadow-sm:    0 1px 3px rgba(10,15,40,.06), 0 1px 2px rgba(10,15,40,.04);
  --dk-shadow-md:    0 4px 12px rgba(10,15,40,.07), 0 2px 4px rgba(10,15,40,.04);
  --dk-ease:         cubic-bezier(0.2, 0.8, 0.2, 1);
}

.dk-pub-page {
  min-height: 100vh;
  background: var(--dk-bg);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  font-size: 14px;
  line-height: 1.5;
  color: var(--dk-text);
  -webkit-font-smoothing: antialiased;
}

.dk-pub-card {
  background: var(--dk-surface);
  border: 1px solid var(--dk-border);
  border-radius: 16px;
  box-shadow: var(--dk-shadow-md);
  width: 100%;
  max-width: 520px;
  padding: 40px;
}

@media (max-width: 640px) {
  .dk-pub-card { padding: 24px; border-radius: 12px; }
  .dk-pub-page { padding: 16px; }
}

.dk-pub-center { text-align: center; }

.dk-pub-icon-large { font-size: 48px; margin-bottom: 16px; }

.dk-pub-title {
  font-size: 20px;
  font-weight: 600;
  color: var(--dk-text);
  margin: 0 0 6px 0;
  letter-spacing: -0.01em;
}

.dk-pub-muted {
  font-size: 13px;
  color: var(--dk-text-muted);
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
  color: var(--dk-text);
}

.dk-pub-checkbox {
  width: 16px;
  height: 16px;
  accent-color: var(--dk-brand-500);
  cursor: pointer;
  flex-shrink: 0;
}

.dk-pub-dsgvo {
  background: var(--dk-surface-2);
  border: 1px solid var(--dk-border);
  border-radius: 10px;
  padding: 14px;
  font-size: 13px;
}

.dk-pub-dsgvo-text {
  color: var(--dk-text-muted);
  margin: 0 0 10px 0;
  line-height: 1.5;
}

.dk-pub-dsgvo-label {
  font-weight: 500;
  color: var(--dk-text);
}

.dk-pub-submit {
  width: 100%;
  background: var(--dk-brand-500) !important;
  border-color: var(--dk-brand-500) !important;
}
.dk-pub-submit:hover {
  background: var(--dk-brand-800) !important;
  border-color: var(--dk-brand-800) !important;
}
</style>
