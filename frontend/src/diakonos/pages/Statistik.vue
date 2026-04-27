<template>
    <div class="dk-screen dk-screen-enter">
        <div class="dk-screen-header">
            <div>
                <h1 class="dk-screen-title">Statistik</h1>
                <p class="dk-screen-sub">Übersicht über wichtige Kennzahlen.</p>
            </div>
        </div>

        <div v-if="loading" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div v-for="n in 4" :key="n" class="dk-skeleton dk-skeleton-card" style="height:112px"></div>
        </div>

        <div v-else class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div class="dk-card p-5 flex flex-col items-center text-center">
                <div class="text-[var(--dk-info)] mb-2">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-8 w-8" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0z" /></svg>
                </div>
                <div class="text-[32px] font-bold text-[var(--dk-text)]">{{ stats.mitglieder }}</div>
                <div class="text-sm text-[var(--dk-text-muted)] mt-1">Mitglieder</div>
            </div>
            <div class="dk-card p-5 flex flex-col items-center text-center">
                <div class="text-[var(--dk-success)] mb-2">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-8 w-8" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0z" /></svg>
                </div>
                <div class="text-[32px] font-bold text-[var(--dk-text)]">{{ stats.gruppen }}</div>
                <div class="text-sm text-[var(--dk-text-muted)] mt-1">Gruppen</div>
            </div>
            <div class="dk-card p-5 flex flex-col items-center text-center">
                <div class="text-[var(--dk-brand-500)] mb-2">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-8 w-8" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>
                </div>
                <div class="text-[32px] font-bold text-[var(--dk-text)]">{{ stats.anmeldungen }}</div>
                <div class="text-sm text-[var(--dk-text-muted)] mt-1">Anmeldungen</div>
            </div>
            <div class="dk-card p-5 flex flex-col items-center text-center">
                <div class="text-[var(--dk-warning)] mb-2">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-8 w-8" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                </div>
                <div class="text-[32px] font-bold text-[var(--dk-text)]">{{ stats.dsgvo }}</div>
                <div class="text-sm text-[var(--dk-text-muted)] mt-1">DSGVO-Einwilligungen</div>
            </div>
        </div>
    </div>
</template>

<script>
import { ref, onMounted } from 'vue'
import { apiCall } from '../composables/useApi.js'

export default {
    name: 'Statistik',
    setup() {
        const loading = ref(true)
        const stats = ref({ mitglieder: 0, gruppen: 0, anmeldungen: 0, dsgvo: 0 })

        onMounted(() => {
            loadStats()
        })

        async function loadStats() {
            loading.value = true
            try {
                const [m, g, s] = await Promise.all([
                    apiCall('diakronos.diakonos.api.mitglieder.get_mitglieder_liste', { limit: 1 }).catch(() => ({ total: 0 })),
                    apiCall('diakronos.diakonos.api.gruppen.get_gruppen_hierarchie').catch(() => ({ gruppen: [] })),
                    apiCall('diakronos.diakonos.api.admin_hub.get_statistik').catch(() => ({ anmeldungen: { gesamt: 0 }, dsgvo: { ok: 0 } })),
                ])
                stats.value.mitglieder = m?.total || 0
                stats.value.gruppen = g?.gruppen?.length || 0
                stats.value.anmeldungen = s?.anmeldungen?.gesamt || 0
                stats.value.dsgvo = s?.dsgvo?.ok || 0
            } catch (e) {
                console.error(e)
            } finally {
                loading.value = false
            }
        }

        return { loading, stats }
    }
}
</script>
