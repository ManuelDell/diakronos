<template>
    <div class="relative w-full h-screen bg-white overflow-hidden">

        <!-- Header -->
        <div class="absolute top-0 left-0 right-0 z-10 flex items-center justify-between px-5 py-3
                    bg-white border-b border-gray-100 shadow-sm">
            <span class="font-semibold text-gray-700">Organigramm</span>
            <div class="flex items-center gap-2">
                <!-- DEP-1: Bild oder Initialen — dasselbe Bild wie in den
                     Organigramm-Knoten (.oc-mitglied-foto / .oc-mitglied-avatar,
                     Tokens aus tokens.css) statt Avatar aus frappe-ui.
                     MT-2b: Das Bild kam aus `window.__diakronos.userImage` —
                     dieses Objekt setzt nur die oeffentliche Datenansicht für
                     `gast`, das Organigramm liest `__DIakonosBOOT` und hatte
                     dort NIE einen Wert (toter Zweig). Entfernt; es bleiben
                     die Initialen aus dem Anzeigenamen. -->
                <span v-if="userFullname" class="oc-kopf-avatar" aria-hidden="true">{{ initials(userFullname) }}</span>
                <span class="text-sm text-gray-600">{{ userFullname }}</span>
            </div>
        </div>

        <!-- UX2d3c (Review UX2d3b): Ladeprosa ersetzt der Platzhalter — und
             wie in den Seiten des Hauptbereichs erst nach 300 ms
             (`useLadeSkelett`), damit er bei schneller Antwort nicht blitzt. -->
        <div v-if="skelettSichtbar" class="oc-laden">
            <DkSkelett form="karten" :anzahl="4" text="Organigramm wird geladen" />
        </div>

        <!-- Fehler -->
        <div v-else-if="fehler" class="oc-laden">
            <DkEmpty icon="!" title="Organigramm nicht geladen" :text="fehler" :erneut-versuchen="laden" />
        </div>

        <!-- Chart-Container -->
        <!-- UX2d3c: Der Chart-Bereich wird erst gezeichnet, wenn Daten da sind —
             sonst läge eine leere Zeichenfläche unter Skelett/Fehlerfläche. -->
        <div
            v-show="!skelettSichtbar && !fehler"
            id="org-chart-container"
            class="w-full h-full pt-14"
        ></div>
    </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
// WEB-5b: Adressen unter dem Betriebs-Praefix (DIAKRONOS_BASE_PATH) bauen.
import { apiUrl } from '../shared/basis.js'
// UX2d3c: Ladeprosa -> Skelett (erst nach 300 ms); Fehlerfläche mit Weg zurück.
import DkSkelett from '../diakonos/components/ui/DkSkelett.vue'
import DkEmpty from '../diakonos/components/ui/DkEmpty.vue'
import { useLadeSkelett } from '../diakonos/composables/useLadeSkelett.js'
import { OrgChart } from 'd3-org-chart'
// UXD-R5: dieselben sicheren Ausgabe-Helfer wie in der Organigramm-Ansicht
// (diakonos/components/gruppen/OrganigrammAnsicht.vue) — keine Kopie.
// d3-org-chart nimmt HTML-Strings, Vue-Escaping greift dort nicht.
import { escapeHtml, sichereBildUrl } from '../shared/sichere-ausgabe.js'
// OP-UI-1: abgelaufene Anmeldung von fehlender Berechtigung unterscheiden —
// dieselben Regeln wie im Hauptbereich, ohne Vue-Abhängigkeit.
import { antwortPruefen } from '../shared/sitzung-pruefen.js'
// UX2g: EINE Quelle fuer angezeigte Fehlertexte (kein "Fehler beim Laden: ...").
import { fehlertext } from '../shared/fehlertexte.js'

const loading     = ref(true)
const fehler      = ref('')
// UX2d3c: Platzhalter erst, wenn das Laden merklich dauert (300 ms).
const { skelettSichtbar } = useLadeSkelett(loading)
const userFullname = window.__diakronos?.userFullname || ''

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

async function laden() {
    loading.value = true
    fehler.value = ''
    try {
        // WEB-8b: derselbe Aufruf, damit eine CSRF-Ablehnung still geheilt
        // werden kann (Token neu + genau eine Wiederholung, sonst Neuladen).
        // Der Token wird je Versuch frisch aus dem meta-Tag gelesen.
        const anfrage = () => fetch(apiUrl('diakronos.diakonos.api.orgchart_api.get_orgchart_data'), {
            credentials: 'same-origin',
            headers: { 'X-Frappe-CSRF-Token': document.querySelector('meta[name="csrf-token"]')?.content || window.csrf_token || '' },
        })
        const res = await anfrage()
        // OP-UI-1: 401/419 leitet zur Anmeldemaske (Rücksprung auf diese
        // Adresse); Rechte-/Serverfehler erscheinen als Klartext.
        const { message: nodes } = await antwortPruefen(res, { anfrage })

        if (!nodes?.length) {
            // UX2d3c: Leerzustand, kein Fehler — aber mit nächstem Schritt
            // (der Fehlerfläche fehlt der Weg; hier gibt es schlicht nichts).
            fehler.value = 'Es sind noch keine Gruppen angelegt.'
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
        // WEB-8d (N4): geprüft wird die MARKIERUNG am Fehler (`e.sitzung`),
        // nicht `instanceof SitzungsFehler`: die Klasse kann aus einem anderen
        // Modul kommen (eigener Bundle-Eintrag, data:-Modul im Test) und
        // `instanceof` wäre dann falsch-negativ.
        if (e?.sitzung) {
            fehler.value = 'Deine Anmeldung ist abgelaufen. Du wirst zur Anmeldung weitergeleitet.'
        } else {
            // UX2g: Katalogtext statt „Fehler beim Laden: <interner Text>".
            fehler.value = fehlertext(e)
        }
    } finally {
        loading.value = false
    }
}

onMounted(laden)
</script>

<style>
/* Eigenständige OrgChart-Oberfläche — Farben/Raumwerte kommen aus tokens.css
   (Import in main.js). Kopierte Token-WERTE sind entfernt: tokens.css ist die
   einzige Quelle (Wächter-Test DS3). */

.oc-node { font-family: inherit; }

/* UX2d3c: Lade-/Fehlerfläche mittig im freien Bereich unter dem Kopf. */
.oc-laden {
    display: flex; align-items: center; justify-content: center;
    height: 100%; padding: calc(var(--sp-8) + var(--sp-6)) var(--pad) var(--sp-6);
}
.oc-node--org {
    background: var(--primary); color: var(--primary-ink); border-radius: var(--radius);
    padding: 14px 20px; text-align: center;
}
.oc-org-name { font-size: var(--fs-16); font-weight: var(--fw-fett); }
.oc-org-meta { font-size: var(--fs-12); opacity: .85; margin-top: 4px; }

.oc-node--gruppe {
    background: var(--surface); border: 2px solid var(--info-soft); border-radius: var(--radius);
    padding: 12px 16px;
}
.oc-gruppe-header { display: flex; align-items: center; gap: 6px; margin-bottom: 4px; }
.oc-gruppe-name { font-size: var(--fs-14); font-weight: var(--fw-fett); color: var(--text); }
.oc-gruppe-typ { font-size: var(--fs-12); background: var(--info-soft); color: var(--info); border-radius: var(--badge-r); padding: 1px 7px; }
.oc-gruppe-leiter { font-size: var(--fs-12); color: var(--muted); }
.oc-gruppe-count { font-size: var(--fs-12); color: var(--subtle); margin-top: 4px; }

.oc-node--mitglied {
    display: flex; align-items: center; gap: 10px;
    background: var(--surface-2); border: 1px solid var(--line); border-radius: var(--radius-sm); padding: 8px 12px;
}
.oc-mitglied-foto { width: 36px; height: 36px; border-radius: 50%; object-fit: cover; }
.oc-mitglied-avatar {
    width: 36px; height: 36px; border-radius: 50%;
    background: var(--info-soft); color: var(--info);
    display: flex; align-items: center; justify-content: center;
    font-size: var(--fs-12); font-weight: var(--fw-fett); flex-shrink: 0;
}

/* DEP-1: Profilbild im Kopf (ersetzt Avatar aus frappe-ui). Kleinere Fassung
   derselben Form wie im Knoten. */
.oc-kopf-foto { width: 26px; height: 26px; border-radius: 50%; object-fit: cover; flex-shrink: 0; }
.oc-kopf-avatar {
    width: 26px; height: 26px; border-radius: 50%;
    background: var(--info-soft); color: var(--info);
    display: flex; align-items: center; justify-content: center;
    font-size: var(--fs-12); font-weight: var(--fw-fett); flex-shrink: 0;
}
.oc-mitglied-name { font-size: var(--fs-14); font-weight: var(--fw-fett); color: var(--text); }
.oc-mitglied-rolle { font-size: var(--fs-12); color: var(--subtle); margin-top: 1px; }
</style>
