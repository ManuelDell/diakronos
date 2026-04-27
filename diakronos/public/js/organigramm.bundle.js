// organigramm.bundle.js – Diakonos OrgChart-Klasse für den Frappe Desk

import { OrgChart } from 'd3-org-chart';

frappe.provide('diakronos');

// ── Helpers ───────────────────────────────────────────────────────────────────
function initials(name) {
    return (name || '').trim().split(/\s+/).map(w => w[0]).join('').slice(0, 2).toUpperCase();
}

function escHtml(s) {
    return (s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function nodeContent(d) {
    const n = d.data;
    if (n.node_type === 'org') {
        return `<div class="oc-node oc-node--org">
            <div class="oc-org-name">${escHtml(n.name)}</div>
            <div class="oc-org-meta">👥 ${n.member_count} Mitglieder</div>
        </div>`;
    }
    if (n.node_type === 'dienstbereich') {
        const iconHtml = n.icon ? `<span class="oc-db-icon">${escHtml(n.icon)}</span>` : '';
        const style = n.farbe ? `border-left: 4px solid ${escHtml(n.farbe)};` : '';
        return `<div class="oc-node oc-node--dienstbereich" style="${style}">
            ${iconHtml}<span class="oc-db-name">${escHtml(n.name)}</span>
        </div>`;
    }
    if (n.node_type === 'gruppe') {
        const leiterHtml = n.leiter
            ? `<div class="oc-gruppe-leiter">Leitung: ${escHtml(n.leiter)}</div>` : '';
        const typHtml = n.gruppentyp
            ? `<span class="oc-gruppe-typ">${escHtml(n.gruppentyp)}</span>` : '';
        return `<div class="oc-node oc-node--gruppe">
            <div class="oc-gruppe-header">
                <span class="oc-gruppe-name">${escHtml(n.name)}</span>${typHtml}
            </div>
            ${leiterHtml}
            <div class="oc-gruppe-count">👥 ${n.member_count}</div>
        </div>`;
    }
    if (n.node_type === 'untergruppe') {
        return `<div class="oc-node oc-node--untergruppe">
            <div class="oc-untergruppe-name">${escHtml(n.name)}</div>
            <div class="oc-gruppe-count">👥 ${n.member_count}</div>
        </div>`;
    }
    if (n.node_type === 'mitglied') {
        const avatarHtml = n.foto
            ? `<img class="oc-mitglied-foto" src="${escHtml(n.foto)}" alt="${escHtml(n.name)}">`
            : `<div class="oc-mitglied-avatar">${initials(n.name)}</div>`;
        const rolleHtml = n.rolle
            ? `<div class="oc-mitglied-rolle">${escHtml(n.rolle)}</div>` : '';
        return `<div class="oc-node oc-node--mitglied">
            ${avatarHtml}
            <div class="oc-mitglied-info">
                <div class="oc-mitglied-name">${escHtml(n.name)}</div>
                ${rolleHtml}
            </div>
        </div>`;
    }
    return `<div class="oc-node">${escHtml(n.name)}</div>`;
}

function nodeHeight(d) {
    if (d.data.node_type === 'org')          return 80;
    if (d.data.node_type === 'dienstbereich') return 60;
    if (d.data.node_type === 'gruppe')        return 90;
    if (d.data.node_type === 'untergruppe')   return 70;
    if (d.data.node_type === 'mitglied')      return 64;
    return 80;
}

function nodeWidth(d) {
    if (d.data.node_type === 'mitglied')      return 200;
    if (d.data.node_type === 'dienstbereich') return 260;
    return 240;
}

// ── Klasse ────────────────────────────────────────────────────────────────────
diakronos.OrgChart = class {
    constructor({ container, onReady } = {}) {
        this.container = container;
        this.chart = null;
        this._memberParents = new Set();
        this._init().then(() => onReady?.());
    }

    async _init() {
        const el = typeof this.container === 'string'
            ? document.querySelector(this.container)
            : this.container;
        if (!el) return;

        el.innerHTML = '<div class="oc-loading">Organigramm wird geladen…</div>';

        let nodes;
        try {
            const res = await frappe.call(
                'diakronos.diakonos.api.orgchart_api.get_orgchart_data'
            );
            nodes = res.message;
        } catch (e) {
            el.innerHTML = `<div class="oc-error">Fehler: ${e.message ?? e}</div>`;
            return;
        }

        if (!nodes?.length) {
            el.innerHTML = '<div class="oc-error">Keine Gruppen gefunden.</div>';
            return;
        }

        el.innerHTML = '';
        this._memberParents = new Set(
            nodes.filter(n => n.node_type === 'mitglied').map(n => n.parentId)
        );

        this.chart = new OrgChart()
            .container(this.container)
            .data(nodes)
            .nodeWidth(nodeWidth)
            .nodeHeight(nodeHeight)
            .childrenMargin(() => 40)
            .siblingsMargin(() => 20)
            .initialExpandLevel(2)
            .nodeContent(nodeContent)
            .onNodeClick(d => {
                if (d.data.node_type === 'gruppe' && this._memberParents.has(d.data.id)) {
                    this.chart.setExpanded(d.data.id, !d._expanded).render().fit();
                }
            })
            .render();
    }

    fit() {
        this.chart?.fit();
    }

    exportPNG() {
        this.chart?.exportImg({ full: true, save: true, scale: 3 });
    }

    exportSVG() {
        if (!this.chart) return;
        // d3-org-chart exportSvg gibt einen SVG-String zurück
        const svgData = this.chart.exportSvg?.();
        if (!svgData) return;
        const blob = new Blob([svgData], { type: 'image/svg+xml' });
        const url  = URL.createObjectURL(blob);
        const a    = document.createElement('a');
        a.href     = url;
        a.download = 'organigramm.svg';
        a.click();
        URL.revokeObjectURL(url);
    }
};
