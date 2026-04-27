<template>
    <div class="dk-screen dk-screen-wide dk-screen-enter">
        <div class="dk-screen-header">
            <div>
                <h1 class="dk-screen-title">Organigramm</h1>
                <p class="dk-screen-sub">Übersicht aller Gruppen und Untergruppen.</p>
            </div>
        </div>

        <div v-if="loading" class="dk-skeleton dk-skeleton-card" style="height:200px"></div>

        <div v-else-if="gruppen.length === 0" class="dk-empty">
            Keine Gruppen vorhanden.
        </div>

        <div v-else class="dk-org-tree">
            <div v-for="g in gruppen" :key="g.name" class="dk-org-group">
                <div class="dk-org-node" @click="goToGruppe(g.name)">
                    <div class="dk-org-node-header">
                        <span class="dk-org-node-name">{{ g.gruppenname }}</span>
                        <span class="dk-org-node-badge">{{ g.mitglieder_count }} Mitglieder</span>
                    </div>
                    <div class="dk-org-node-meta">{{ g.dienstbereich }} · {{ g.gruppentyp || 'Gruppe' }}</div>
                </div>
                <div v-if="g.untergruppen?.length" class="dk-org-children">
                    <div v-for="u in g.untergruppen" :key="u.name" class="dk-org-node dk-org-sub-node" @click="goToGruppe(u.name)">
                        <div class="dk-org-node-header">
                            <span class="dk-org-node-name">{{ u.untergruppenname }}</span>
                            <span class="dk-org-node-badge">{{ u.mitglieder_count }} Mitglieder</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>

<script>
import { ref, onMounted } from 'vue'
import { apiCall } from '../composables/useApi.js'

export default {
    name: 'Organigramm',
    setup() {
        const loading = ref(true)
        const gruppen = ref([])

        onMounted(() => {
            loadGruppen()
        })

        async function loadGruppen() {
            loading.value = true
            try {
                const data = await apiCall('diakronos.diakonos.api.gruppen.get_gruppen_hierarchie')
                gruppen.value = data?.gruppen || []
            } catch (e) {
                console.error(e)
            } finally {
                loading.value = false
            }
        }

        function goToGruppe(id) {
            window.location.hash = '#/gruppe/' + encodeURIComponent(id)
        }

        return { loading, gruppen, goToGruppe }
    }
}
</script>
