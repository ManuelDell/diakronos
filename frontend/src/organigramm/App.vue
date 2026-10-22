<template>
    <div class="relative w-full h-screen bg-white overflow-hidden">

        <!-- Header -->
        <div class="absolute top-0 left-0 right-0 z-10 flex items-center justify-between px-5 py-3
                    bg-white border-b border-gray-100 shadow-sm">
            <span class="font-semibold text-gray-700">Organigramm</span>
            <div class="flex items-center gap-2">
                <Avatar
                    v-if="userImage"
                    :image="userImage"
                    :label="userFullname"
                    size="sm"
                />
                <span class="text-sm text-gray-600">{{ userFullname }}</span>
            </div>
        </div>

        <!-- Loading -->
        <div v-if="loading" class="flex items-center justify-center h-full text-gray-400">
            <Spinner class="w-6 h-6 mr-2" />
            Organigramm wird geladen…
        </div>

        <!-- Fehler -->
        <div v-else-if="fehler" class="flex items-center justify-center h-full">
            <div class="text-center text-gray-500">
                <div class="text-4xl mb-3">⚠️</div>
                <p>{{ fehler }}</p>
            </div>
        </div>

        <!-- Chart-Container -->
        <div
            id="org-chart-container"
            class="w-full h-full pt-14"
        ></div>
    </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { Spinner, Avatar } from 'frappe-ui'
import { OrgChart } from 'd3-org-chart'
// UXD-R5: dieselben sicheren Ausgabe-Helfer wie in der Organigramm-Ansicht
// (diakonos/components/gruppen/OrganigrammAnsicht.vue) — keine Kopie.
// d3-org-chart nimmt HTML-Strings, Vue-Escaping greift dort nicht.
import { escapeHtml, sichereBildUrl } from '../shared/sichere-ausgabe.js'
// OP-UI-1: abgelaufene Anmeldung von fehlender Berechtigung unterscheiden —
// dieselben Regeln wie im Hauptbereich, ohne Vue-Abhängigkeit.
import { antwortPruefen, SitzungsFehler } from '../shared/sitzung-pruefen.js'

const loading     = ref(true)
const fehler      = ref('')
const userFullname = window.__diakronos?.userFullname || ''
const userImage    = window.__diakronos?.userImage || ''
const csrf         = document.querySelector('meta[name="csrf-token"]')?.content
                   || window.csrf_token || ''

function initials(name) {
    return name.trim().split(/\s+/).map(w => w[0]).join('').slice(0, 2).toUpperCase()
}

function nodeContent(d) {
    const n = d.data
    if (n.node_type === 'org') {
        return `<div class="oc-node oc-node--org">
            <div class="oc-org-name">${escapeHtml(n.name)}</div>
            <div class="oc-org-meta">👥 ${escapeHtml(n.member_count)} Mitglieder</div>
        </div>`
    }
    if (n.node_type === 'gruppe') {
        const leiterHtml = n.leiter ? `<div class="oc-gruppe-leiter">Leitung: ${escapeHtml(n.leiter)}</div>` : ''
        const typHtml    = n.gruppentyp ? `<span class="oc-gruppe-typ">${escapeHtml(n.gruppentyp)}</span>` : ''
        return `<div class="oc-node oc-node--gruppe">
            <div class="oc-gruppe-header"><span class="oc-gruppe-name">${escapeHtml(n.name)}</span>${typHtml}</div>
            ${leiterHtml}
            <div class="oc-gruppe-count">👥 ${escapeHtml(n.member_count)}</div>
        </div>`
    }
    if (n.node_type === 'mitglied') {
        // UXD-R5: nur http(s)/relative URL, sonst der Initialen-Kreis.
        const fotoUrl = sichereBildUrl(n.foto)
        const avatarHtml = fotoUrl
            ? `<img class="oc-mitglied-foto" src="${fotoUrl}" alt="${escapeHtml(n.name)}">`
            : `<div class="oc-mitglied-avatar">${escapeHtml(initials(n.name))}</div>`
        const rolleHtml = n.rolle ? `<div class="oc-mitglied-rolle">${escapeHtml(n.rolle)}</div>` : ''
        return `<div class="oc-node oc-node--mitglied">
            ${avatarHtml}
            <div class="oc-mitglied-info">
                <div class="oc-mitglied-name">${escapeHtml(n.name)}</div>
                ${rolleHtml}
            </div>
        </div>`
    }
    return `<div class="oc-node">${escapeHtml(n.name)}</div>`
}

function nodeHeight(d) {
    if (d.data.node_type === 'org')      return 80
    if (d.data.node_type === 'gruppe')   return 90
    if (d.data.node_type === 'mitglied') return 64
    return 80
}

function nodeWidth(d) {
    return d.data.node_type === 'mitglied' ? 200 : 240
}

onMounted(async () => {
    try {
        const res = await fetch('/api/method/diakronos.diakonos.api.orgchart_api.get_orgchart_data', {
            headers: { 'X-Frappe-CSRF-Token': csrf },
        })
        // OP-UI-1: 401/419 leitet zur Anmeldemaske (Rücksprung auf diese
        // Adresse); Rechte-/Serverfehler erscheinen als Klartext.
        const { message: nodes } = await antwortPruefen(res)

        if (!nodes?.length) {
            fehler.value = 'Keine Gruppen gefunden.'
            return
        }

        const memberParents = new Set(
            nodes.filter(n => n.node_type === 'mitglied').map(n => n.parentId)
        )

        const chart = new OrgChart()
            .container('#org-chart-container')
            .data(nodes)
            .nodeWidth(nodeWidth)
            .nodeHeight(nodeHeight)
            .childrenMargin(() => 40)
            .siblingsMargin(() => 20)
            .initialExpandLevel(2)
            .nodeContent(nodeContent)
            .onNodeClick(d => {
                if (d.data.node_type === 'gruppe' && memberParents.has(d.data.id)) {
                    chart.setExpanded(d.data.id, !d._expanded).render().fit()
                }
            })
            .render()
    } catch (e) {
        // Sitzungsabbruch leitet bereits um — dann keine irreführende
        // Fehlerfläche („Fehler beim Laden: 401") stehen lassen.
        if (e instanceof SitzungsFehler) {
            fehler.value = 'Deine Anmeldung ist abgelaufen. Du wirst zur Anmeldung weitergeleitet.'
        } else {
            fehler.value = `Fehler beim Laden: ${e.message}`
        }
    } finally {
        loading.value = false
    }
})
</script>

<style>
/* Eigenständige OrgChart-Oberfläche — Farben/Raumwerte kommen aus tokens.css
   (Import in main.js). Kopierte Token-WERTE sind entfernt: tokens.css ist die
   einzige Quelle (Wächter-Test DS3). */

.oc-node { font-family: inherit; }
.oc-node--org {
    background: var(--primary); color: var(--primary-ink); border-radius: var(--radius);
    padding: 14px 20px; text-align: center;
}
.oc-org-name { font-size: .95rem; font-weight: 700; }
.oc-org-meta { font-size: .78rem; opacity: .85; margin-top: 4px; }

.oc-node--gruppe {
    background: var(--surface); border: 2px solid var(--info-soft); border-radius: var(--radius);
    padding: 12px 16px;
}
.oc-gruppe-header { display: flex; align-items: center; gap: 6px; margin-bottom: 4px; }
.oc-gruppe-name { font-size: .9rem; font-weight: 700; color: var(--text); }
.oc-gruppe-typ { font-size: .72rem; background: var(--info-soft); color: var(--info); border-radius: var(--badge-r); padding: 1px 7px; }
.oc-gruppe-leiter { font-size: .78rem; color: var(--muted); }
.oc-gruppe-count { font-size: .78rem; color: var(--subtle); margin-top: 4px; }

.oc-node--mitglied {
    display: flex; align-items: center; gap: 10px;
    background: var(--surface-2); border: 1px solid var(--line); border-radius: var(--radius-sm); padding: 8px 12px;
}
.oc-mitglied-foto { width: 36px; height: 36px; border-radius: 50%; object-fit: cover; }
.oc-mitglied-avatar {
    width: 36px; height: 36px; border-radius: 50%;
    background: var(--info-soft); color: var(--info);
    display: flex; align-items: center; justify-content: center;
    font-size: .78rem; font-weight: 700; flex-shrink: 0;
}
.oc-mitglied-name { font-size: .82rem; font-weight: 600; color: var(--text); }
.oc-mitglied-rolle { font-size: .72rem; color: var(--subtle); margin-top: 1px; }
</style>
