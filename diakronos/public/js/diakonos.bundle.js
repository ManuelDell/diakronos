// diakonos.bundle.js – Organigramm-Seite

import { OrgChart } from 'd3-org-chart';

const csrf = document.querySelector('meta[name="csrf-token"]')?.content || '';

// ── Initialen-Avatar ─────────────────────────────────────────────────────────
function initials(name) {
    return name.trim().split(/\s+/).map(w => w[0]).join('').slice(0, 2).toUpperCase();
}

// ── Node-Card HTML ───────────────────────────────────────────────────────────
function nodeContent(d) {
    const n = d.data;
    if (n.node_type === 'org') {
        return `
        <div class="oc-node oc-node--org">
            <div class="oc-org-name">${n.name}</div>
            <div class="oc-org-meta">👥 ${n.member_count} Mitglieder</div>
        </div>`;
    }
    if (n.node_type === 'gruppe') {
        const leiterHtml = n.leiter
            ? `<div class="oc-gruppe-leiter">Leitung: ${n.leiter}</div>`
            : '';
        const typHtml = n.gruppentyp
            ? `<span class="oc-gruppe-typ">${n.gruppentyp}</span>`
            : '';
        return `
        <div class="oc-node oc-node--gruppe">
            <div class="oc-gruppe-header">
                <span class="oc-gruppe-name">${n.name}</span>
                ${typHtml}
            </div>
            ${leiterHtml}
            <div class="oc-gruppe-count">👥 ${n.member_count}</div>
        </div>`;
    }
    if (n.node_type === 'mitglied') {
        const avatarHtml = n.foto
            ? `<img class="oc-mitglied-foto" src="${n.foto}" alt="${n.name}">`
            : `<div class="oc-mitglied-avatar">${initials(n.name)}</div>`;
        const rolleHtml = n.rolle
            ? `<div class="oc-mitglied-rolle">${n.rolle}</div>`
            : '';
        return `
        <div class="oc-node oc-node--mitglied">
            ${avatarHtml}
            <div class="oc-mitglied-info">
                <div class="oc-mitglied-name">${n.name}</div>
                ${rolleHtml}
            </div>
        </div>`;
    }
    return `<div class="oc-node">${n.name}</div>`;
}

// ── Chart-Höhe je Typ ────────────────────────────────────────────────────────
function nodeHeight(d) {
    if (d.data.node_type === 'org')      return 80;
    if (d.data.node_type === 'gruppe')   return 90;
    if (d.data.node_type === 'mitglied') return 64;
    return 80;
}

function nodeWidth(d) {
    if (d.data.node_type === 'mitglied') return 200;
    return 240;
}

// ── Haupt-Logik ──────────────────────────────────────────────────────────────
async function init() {
    const container = document.getElementById('org-chart-container');
    if (!container) return;

    // Lade-Indikator
    container.innerHTML = '<div class="oc-loading">Organigramm wird geladen…</div>';

    let nodes;
    try {
        const res = await fetch(
            '/api/method/diakronos.diakonos.api.orgchart_api.get_orgchart_data',
            { headers: { 'X-Frappe-CSRF-Token': csrf } }
        );
        if (!res.ok) throw new Error(res.status);
        ({ message: nodes } = await res.json());
    } catch (e) {
        container.innerHTML = `<div class="oc-error">Fehler beim Laden: ${e.message}</div>`;
        return;
    }

    if (!nodes?.length) {
        container.innerHTML = '<div class="oc-error">Keine Gruppen gefunden.</div>';
        return;
    }

    container.innerHTML = '';

    // Mitglieder-Knoten merken (für Toggle-Logik)
    const memberParents = new Set(
        nodes.filter(n => n.node_type === 'mitglied').map(n => n.parentId)
    );

    const chart = new OrgChart()
        .container('#org-chart-container')
        .data(nodes)
        .nodeWidth(nodeWidth)
        .nodeHeight(nodeHeight)
        .childrenMargin(() => 40)
        .siblingsMargin(() => 20)
        .initialExpandLevel(2)   // Root + Gruppen aufgeklappt, Mitglieder collapsed
        .nodeContent(nodeContent)
        .onNodeClick(d => {
            // Klick auf Gruppe: Mitglieder ein-/ausblenden
            if (d.data.node_type === 'gruppe' && memberParents.has(d.data.id)) {
                chart.setExpanded(d.data.id, !d._expanded).render().fit();
            }
        })
        .render();
}

init();
