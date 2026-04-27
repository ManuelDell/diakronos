<template>
    <div class="dk-screen dk-screen-enter">
        <h1 class="text-2xl font-bold mb-2">DSGVO</h1>
        <p class="text-[var(--dk-text-muted)] mb-6">Datenschutz-Grundverordnung – Einwilligungen & Widerruf</p>

        <div v-if="loading" class="dk-skeleton dk-skeleton-card" style="height:160px"></div>

        <div v-else class="dk-card p-6 max-w-[600px]">
            <div class="flex items-center gap-3 mb-4">
                <div class="icon-circle" :class="einwilligung.aktiv ? 'bg-[color-mix(in_oklch,var(--dk-success)_12%,var(--dk-surface))] text-[var(--dk-success)]' : 'bg-[color-mix(in_oklch,var(--dk-danger)_12%,var(--dk-surface))] text-[var(--dk-danger)]'">
                    <svg v-if="einwilligung.aktiv" xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" /></svg>
                    <svg v-else xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
                </div>
                <div>
                    <div class="font-semibold text-[var(--dk-text)]">Einwilligungs-Status</div>
                    <div class="text-sm" :class="einwilligung.aktiv ? 'text-[var(--dk-success)]' : 'text-[var(--dk-danger)]'">
                        {{ einwilligung.aktiv ? 'Aktiv' : 'Nicht vorhanden' }}
                    </div>
                </div>
            </div>

            <div v-if="einwilligung.datum" class="text-sm text-[var(--dk-text-muted)] mb-4">
                Einwilligt seit: {{ einwilligung.datum }}
            </div>

            <div class="bg-[var(--dk-surface-2)] p-4 rounded-lg text-sm text-[var(--dk-text-muted)] leading-relaxed mb-4">
                <p class="mb-2"><strong>Hinweis:</strong> Mit Ihrer Einwilligung erlauben Sie der Gemeinde, Ihre personenbezogenen Daten zu verarbeiten.</p>
                <p>Sie können Ihre Einwilligung jederzeit mit Wirkung für die Zukunft widerrufen. Ein Widerruf lässt die Rechtmäßigkeit der bis dahin erfolgten Verarbeitung unberührt.</p>
            </div>

            <button
                v-if="isAdminMode"
                class="dk-btn dk-btn-danger"
                @click="widerrufen"
                :disabled="!einwilligung.aktiv || revoking"
            >
                {{ revoking ? 'Widerruf wird durchgeführt...' : 'Einwilligung widerrufen' }}
            </button>
        </div>
    </div>
</template>

<script>
import { ref, onMounted } from 'vue'
import { useSession } from '../composables/useSession.js'
import { apiCall } from '../composables/useApi.js'

import { showToast } from '../composables/useToast.js'

export default {
    name: 'Dsgvo',
    setup() {
        const { isAdminMode } = useSession()
        const loading = ref(true)
        const revoking = ref(false)
        const einwilligung = ref({ aktiv: false, datum: null })
        const mitgliedId = ref(null)

        onMounted(() => {
            loadDsgvo()
        })

        async function loadDsgvo() {
            loading.value = true
            try {
                const ctx = await apiCall('diakronos.diakonos.api.session.get_current_user_context')
                const mitglied = ctx?.mitglied
                mitgliedId.value = mitglied?.name || null
                einwilligung.value.aktiv = mitglied?.datenschutz_einwilligung ? true : false
                einwilligung.value.datum = mitglied?.datenschutz_datum || null
            } catch (e) {
                console.error(e)
            } finally {
                loading.value = false
            }
        }

        async function widerrufen() {
            if (!mitgliedId.value) {
                showToast('Kein Mitglied gefunden', 'error')
                return
            }
            revoking.value = true
            try {
                const res = await apiCall('diakronos.diakonos.api.mitglieder.widerruf_einwilligung', {
                    mitglied_id: mitgliedId.value,
                })
                if (res?.success) {
                    showToast(res.message || 'Einwilligung widerrufen', 'success')
                    await loadDsgvo()
                } else {
                    showToast(res?.message || 'Fehler beim Widerruf', 'error')
                }
            } catch (err) {
                showToast(err?.message || 'Fehler beim Widerruf', 'error')
            } finally {
                revoking.value = false
            }
        }

        return { loading, revoking, einwilligung, isAdminMode, widerrufen }
    }
}
</script>

<style scoped>
.icon-circle {
    width: 40px; height: 40px;
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
}
</style>
