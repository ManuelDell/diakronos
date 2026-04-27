<template>
    <div class="min-h-screen bg-gray-50 flex items-center justify-center p-4">
        <div class="bg-white rounded-2xl shadow-md w-full max-w-sm p-8">

            <!-- Fehler-Seite -->
            <div v-if="linkFehler" class="text-center">
                <div class="text-5xl mb-4">🔒</div>
                <h1 class="text-xl font-semibold mb-2">Zugang nicht möglich</h1>
                <p class="text-gray-500 text-sm">{{ linkFehler }}</p>
            </div>

            <!-- Erfolgseite -->
            <div v-else-if="success" class="text-center">
                <div class="text-5xl mb-4">✅</div>
                <h1 class="text-xl font-semibold mb-2">Anmeldung übermittelt!</h1>
                <p class="text-gray-500 text-sm">Danke! Deine Anmeldung wurde übermittelt.</p>
            </div>

            <!-- Formular -->
            <template v-else>
                <h1 class="text-xl font-semibold mb-1">Gast-Anmeldung</h1>
                <p class="text-gray-500 text-sm mb-6 leading-relaxed">
                    Schnell und einfach – nur dein Name und eine kurze Datenschutzzustimmung.
                </p>

                <ErrorMessage v-if="fehler" :message="fehler" class="mb-4" />

                <form @submit.prevent="absenden" class="space-y-4" novalidate>
                    <FormControl type="text" label="Vorname *" v-model="form.vorname" autocomplete="given-name" />
                    <FormControl type="text" label="Nachname *" v-model="form.nachname" autocomplete="family-name" />

                    <!-- DSGVO -->
                    <div class="bg-gray-50 border border-gray-200 rounded-xl p-3 text-sm">
                        <p class="text-gray-600 mb-2 leading-relaxed text-xs">
                            Dein Name wird zum Zweck der Anwesenheitsverwaltung gespeichert
                            (Art.&nbsp;6 Abs.&nbsp;1 lit.&nbsp;a DSGVO). Keine Weitergabe an Dritte.
                        </p>
                        <label class="flex items-start gap-2 cursor-pointer">
                            <input
                                type="checkbox"
                                v-model="form.dsgvo"
                                class="mt-0.5 w-4 h-4 shrink-0 accent-emerald-500"
                            />
                            <span class="text-gray-700 font-medium text-xs">Ich stimme zu. *</span>
                        </label>
                    </div>

                    <Button
                        type="submit"
                        variant="solid"
                        class="w-full"
                        :loading="loading"
                        theme="green"
                    >
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
