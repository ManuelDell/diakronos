/**
 * Google Kalender Import – Desk Page
 * =====================================
 * Zweistufige Oberfläche:
 *   Tab 1: Google OAuth2 Import (3-Schritt-Wizard)
 *   Tab 2: iCal-Datei Upload
 */

frappe.pages["google-kalender-import"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({
        parent:    wrapper,
        title:     "Google Kalender Import",
        single_column: true,
    });

    // Bestehende Kalender aus Frappe für Mapping laden
    let frappKalender = [];
    frappe.db.get_list("Kalender", {fields: ["name", "calendar_name"], limit: 100})
        .then(list => { frappKalender = list; });

    // Seite aufbauen
    $(wrapper).find(".page-content").html(renderPageHTML());
    initPage(wrapper);

    // Nach OAuth-Redirect: URL-Parameter auswerten
    const urlParams = new URLSearchParams(window.location.search);
    const gcalStep  = urlParams.get("gcal_step");
    const gcalError = urlParams.get("gcal_error");

    // URL-Parameter sofort bereinigen (ohne Reload)
    if (gcalStep || gcalError) {
        const cleanUrl = window.location.pathname;
        window.history.replaceState({}, "", cleanUrl);
    }

    if (gcalError) {
        // Fehler vom Callback anzeigen
        loadStatus(wrapper, gcalError);
    } else if (gcalStep === "2") {
        loadStep3(wrapper);
    } else {
        loadStatus(wrapper);
    }
};


// ── HTML-Gerüst ─────────────────────────────────────────────────────────────

function renderPageHTML() {
    return `
<div class="gki-container">

    <!-- Tab-Leiste -->
    <div class="gki-tabs">
        <button class="gki-tab active" data-tab="google">
            <span class="gki-tab-icon">🔗</span> Google OAuth2
        </button>
        <button class="gki-tab" data-tab="ical">
            <span class="gki-tab-icon">📁</span> iCal-Datei hochladen
        </button>
    </div>

    <!-- Tab: Google OAuth -->
    <div class="gki-panel" id="gki-panel-google">
        <div id="gki-step-area">
            <div class="gki-loading">Verbindungsstatus wird geprüft…</div>
        </div>
    </div>

    <!-- Tab: iCal Upload -->
    <div class="gki-panel gki-hidden" id="gki-panel-ical">
        <div class="gki-section">
            <h3 class="gki-section-title">iCal-Datei importieren (.ics)</h3>
            <p class="gki-hint">Exportiere einen Kalender aus Google, Outlook, Apple Kalender o.ä. als .ics-Datei und lade ihn hier hoch.</p>

            <div class="gki-form-group">
                <label class="gki-label">Ziel-Kalender</label>
                <div class="gki-radio-row">
                    <label class="gki-radio-label">
                        <input type="radio" name="ical_mode" value="new" checked>
                        Neuen Kalender anlegen
                    </label>
                    <label class="gki-radio-label">
                        <input type="radio" name="ical_mode" value="existing">
                        Bestehenden Kalender nutzen
                    </label>
                </div>
            </div>

            <div id="ical-new-fields">
                <div class="gki-form-row">
                    <div class="gki-form-group">
                        <label class="gki-label">Name des neuen Kalenders</label>
                        <input type="text" id="ical-cal-name" class="gki-input" placeholder="z. B. Gemeindekalender 2024">
                    </div>
                    <div class="gki-form-group gki-form-group--color">
                        <label class="gki-label">Farbe</label>
                        <input type="color" id="ical-cal-color" class="gki-color-input" value="#4285F4">
                    </div>
                </div>
            </div>

            <div id="ical-existing-fields" class="gki-hidden">
                <div class="gki-form-group">
                    <label class="gki-label">Bestehender Kalender</label>
                    <select id="ical-existing-select" class="gki-select">
                        <option value="">— Kalender wählen —</option>
                    </select>
                </div>
            </div>

            <div class="gki-form-group">
                <label class="gki-label">iCal-Datei (.ics)</label>
                <input type="file" id="ical-file-input" class="gki-file-input" accept=".ics">
            </div>

            <button id="ical-import-btn" class="gki-btn gki-btn--primary">
                Kalender importieren
            </button>

            <div id="ical-result" class="gki-result gki-hidden"></div>
        </div>
    </div>

</div>

<style>
/* ── Container ── */
.gki-container { max-width: 760px; margin: 24px auto; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }

/* ── Tabs ── */
.gki-tabs { display: flex; gap: 4px; margin-bottom: 20px; border-bottom: 2px solid #e8e8e8; }
.gki-tab {
    padding: 10px 20px; border: none; background: none; cursor: pointer;
    font-size: 14px; font-weight: 500; color: #666; border-bottom: 2px solid transparent;
    margin-bottom: -2px; transition: all 0.15s;
}
.gki-tab.active { color: #4285F4; border-bottom-color: #4285F4; }
.gki-tab:hover:not(.active) { color: #333; }
.gki-tab-icon { margin-right: 6px; }

/* ── Panel ── */
.gki-panel { background: white; border-radius: 10px; padding: 28px; box-shadow: 0 1px 8px rgba(0,0,0,0.08); }
.gki-hidden { display: none !important; }

/* ── Schritt-Karten ── */
.gki-step-card { border: 1px solid #e8e8e8; border-radius: 8px; padding: 24px; margin-bottom: 16px; }
.gki-step-title { font-size: 16px; font-weight: 600; margin: 0 0 8px; display: flex; align-items: center; gap: 10px; }
.gki-step-num { background: #4285F4; color: white; border-radius: 50%; width: 26px; height: 26px; display: inline-flex; align-items: center; justify-content: center; font-size: 13px; flex-shrink: 0; }
.gki-step-done .gki-step-num { background: #34a853; }
.gki-step-desc { color: #555; font-size: 14px; margin: 0 0 16px; }

/* ── Redirect URI Box ── */
.gki-uri-box { background: #f0f4ff; border: 1px solid #c5d5ff; border-radius: 6px; padding: 10px 14px; font-family: monospace; font-size: 13px; word-break: break-all; margin-bottom: 12px; }

/* ── Formular ── */
.gki-section-title { font-size: 16px; font-weight: 600; margin: 0 0 8px; }
.gki-hint { color: #666; font-size: 13px; margin-bottom: 20px; }
.gki-form-group { margin-bottom: 16px; }
.gki-form-group--color { max-width: 100px; }
.gki-form-row { display: flex; gap: 16px; align-items: flex-start; }
.gki-label { display: block; font-size: 13px; font-weight: 500; color: #444; margin-bottom: 6px; }
.gki-input { width: 100%; padding: 8px 12px; border: 1px solid #d1d5db; border-radius: 6px; font-size: 14px; box-sizing: border-box; }
.gki-input:focus, .gki-select:focus { outline: none; border-color: #4285F4; box-shadow: 0 0 0 3px rgba(66,133,244,0.15); }
.gki-select { width: 100%; padding: 8px 12px; border: 1px solid #d1d5db; border-radius: 6px; font-size: 14px; background: white; box-sizing: border-box; }
.gki-color-input { width: 100%; height: 38px; border: 1px solid #d1d5db; border-radius: 6px; padding: 2px; cursor: pointer; box-sizing: border-box; }
.gki-file-input { display: block; font-size: 14px; }
.gki-radio-row { display: flex; gap: 20px; }
.gki-radio-label { font-size: 14px; cursor: pointer; }

/* ── Buttons ── */
.gki-btn { padding: 10px 22px; border: none; border-radius: 6px; font-size: 14px; font-weight: 500; cursor: pointer; transition: background 0.15s; }
.gki-btn--primary { background: #4285F4; color: white; }
.gki-btn--primary:hover { background: #3367d6; }
.gki-btn--primary:disabled { background: #9ab8f5; cursor: default; }
.gki-btn--secondary { background: #f1f3f4; color: #333; }
.gki-btn--secondary:hover { background: #e8eaed; }
.gki-btn--google { background: white; color: #444; border: 1px solid #dadce0; display: flex; align-items: center; gap: 10px; }
.gki-btn--google:hover { background: #f5f5f5; }
.gki-btn--google svg { flex-shrink: 0; }
.gki-btn-row { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 12px; }

/* ── Kalender-Liste ── */
.gki-cal-list { margin: 16px 0; }
.gki-cal-item { border: 1px solid #e8e8e8; border-radius: 8px; padding: 14px 16px; margin-bottom: 10px; display: grid; grid-template-columns: auto 1fr auto auto; gap: 12px; align-items: center; }
.gki-cal-checkbox { width: 18px; height: 18px; cursor: pointer; }
.gki-cal-info { }
.gki-cal-name { font-weight: 500; font-size: 14px; }
.gki-cal-badge { font-size: 11px; background: #e8f5e9; color: #2e7d32; padding: 2px 6px; border-radius: 10px; margin-left: 6px; }
.gki-cal-dot { width: 14px; height: 14px; border-radius: 50%; flex-shrink: 0; }
.gki-cal-target { display: flex; flex-direction: column; gap: 6px; }
.gki-cal-select, .gki-cal-timefilter { padding: 6px 10px; border: 1px solid #d1d5db; border-radius: 6px; font-size: 13px; background: white; }

/* ── Ergebnis ── */
.gki-result { margin-top: 16px; padding: 14px 16px; border-radius: 8px; font-size: 14px; }
.gki-result--success { background: #e8f5e9; border: 1px solid #a5d6a7; color: #2e7d32; }
.gki-result--error   { background: #fce4ec; border: 1px solid #f48fb1; color: #b71c1c; }
.gki-result-title { font-weight: 600; margin-bottom: 6px; }
.gki-result-detail { line-height: 1.6; }

/* ── Loading ── */
.gki-loading { color: #666; font-style: italic; padding: 20px 0; }

/* ── Progress ── */
.gki-progress-row { display: flex; align-items: center; gap: 14px; padding: 14px 0 4px; }
.gki-progress-spinner { width: 20px; height: 20px; border: 3px solid #e0e0e0; border-top-color: #4285F4; border-radius: 50%; animation: gki-spin 0.8s linear infinite; flex-shrink: 0; }
@keyframes gki-spin { to { transform: rotate(360deg); } }
.gki-progress-text { font-size: 14px; line-height: 1.7; }
</style>
`;
}


// ── Initialisierung ─────────────────────────────────────────────────────────

function initPage(wrapper) {
    // Tab-Switching
    $(wrapper).on("click", ".gki-tab", function () {
        const tab = $(this).data("tab");
        $(wrapper).find(".gki-tab").removeClass("active");
        $(this).addClass("active");
        $(wrapper).find(".gki-panel").addClass("gki-hidden");
        $(wrapper).find(`#gki-panel-${tab}`).removeClass("gki-hidden");
    });

    // iCal: Radio-Buttons für Ziel-Kalender-Modus
    $(wrapper).on("change", "input[name='ical_mode']", function () {
        const mode = $("input[name='ical_mode']:checked").val();
        if (mode === "new") {
            $("#ical-new-fields").show();
            $("#ical-existing-fields").hide();
        } else {
            $("#ical-new-fields").hide();
            $("#ical-existing-fields").show();
            loadExistingKalender();
        }
    });

    // iCal: Import-Button
    $(wrapper).on("click", "#ical-import-btn", function () {
        handleIcalImport(wrapper);
    });
}


// ── Schritt-Steuerung ───────────────────────────────────────────────────────

function loadStatus(wrapper, callbackError) {
    frappe.call({
        method: "diakronos.kronos.api.google_import.get_credentials_status",
        callback: function (r) {
            const status = r.message || {};
            if (!status.configured) {
                renderStep1(wrapper);
            } else if (!status.authorized) {
                renderStep2(wrapper, status.redirect_uri, callbackError);
            } else {
                loadStep3(wrapper);
            }
        },
        error: function () {
            $("#gki-step-area").html('<p class="text-danger">Fehler beim Laden des Status.</p>');
        },
    });
}


function renderStep1(wrapper) {
    // Standard-Redirect-URI vorschlagen
    const defaultUri = `${window.location.origin}/google-calendar-callback`;

    const html = `
<div class="gki-step-card" id="gki-step1">
    <div class="gki-step-title">
        <span class="gki-step-num">1</span>
        Google API Zugangsdaten eingeben
    </div>
    <p class="gki-step-desc">
        Du brauchst ein Google Cloud Projekt mit aktivierter Google Calendar API und einem OAuth 2.0 Client (Typ: Webanwendung).
    </p>
    <div class="gki-form-group">
        <label class="gki-label">Client ID</label>
        <input type="text" id="gki-client-id" class="gki-input" placeholder="xxxxx.apps.googleusercontent.com">
    </div>
    <div class="gki-form-group">
        <label class="gki-label">Client Secret</label>
        <input type="password" id="gki-client-secret" class="gki-input" placeholder="GOCSPX-…">
    </div>
    <div class="gki-form-group">
        <label class="gki-label">
            Redirect URI
            <span style="font-weight:400; color:#666"> – muss exakt so in der Google Console eingetragen sein</span>
        </label>
        <input type="text" id="gki-redirect-uri" class="gki-input" value="${defaultUri}">
    </div>
    <button class="gki-btn gki-btn--primary" id="gki-save-creds-btn">Speichern & Weiter</button>
</div>`;
    $("#gki-step-area").html(html);

    $(wrapper).on("click", "#gki-save-creds-btn", function () {
        const client_id     = $("#gki-client-id").val().trim();
        const client_secret = $("#gki-client-secret").val().trim();
        const redirect_uri  = $("#gki-redirect-uri").val().trim();
        if (!client_id || !client_secret) {
            frappe.msgprint("Bitte Client ID und Client Secret eingeben.");
            return;
        }
        if (!redirect_uri) {
            frappe.msgprint("Bitte die Redirect URI eingeben.");
            return;
        }
        $(this).text("Speichern…").prop("disabled", true);
        frappe.call({
            method: "diakronos.kronos.api.google_import.save_credentials",
            args: { client_id, client_secret, redirect_uri },
            callback: function () {
                renderStep2(wrapper, redirect_uri);
            },
        });
    });
}


function renderStep2(wrapper, knownRedirectUri, callbackError) {
    const errorHtml = callbackError ? `
<div class="gki-result gki-result--error" style="margin-bottom:12px">
    <div class="gki-result-title">❌ Verbindung fehlgeschlagen</div>
    <div class="gki-result-detail">${frappe.utils.escape_html(callbackError)}</div>
</div>` : "";

    const html = `
<div class="gki-step-card gki-step-done" id="gki-step1-done">
    <div class="gki-step-title">
        <span class="gki-step-num">✓</span>
        Zugangsdaten gespeichert
    </div>
    <p class="gki-step-desc" style="margin:0">
        <a href="#" id="gki-reset-creds">Zugangsdaten ändern</a>
    </p>
</div>

<div class="gki-step-card" id="gki-step2">
    <div class="gki-step-title">
        <span class="gki-step-num">2</span>
        Mit Google anmelden
    </div>
    ${errorHtml}
    <p class="gki-step-desc">
        Klicke auf den Button und melde dich mit dem Google-Account an, dessen Kalender importiert werden sollen.
        Du wirst nach dem Login automatisch zurückgeleitet.
    </p>
    <div class="gki-btn-row">
        <button class="gki-btn gki-btn--google" id="gki-connect-btn">
            <svg width="18" height="18" viewBox="0 0 48 48">
                <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/>
                <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/>
                <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/>
                <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.18 1.48-4.97 2.29-8.16 2.29-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/>
            </svg>
            Mit Google anmelden
        </button>
    </div>
</div>`;

    $("#gki-step-area").html(html);

    $(wrapper).on("click", "#gki-reset-creds", function (e) {
        e.preventDefault();
        renderStep1(wrapper);
    });

    $(wrapper).on("click", "#gki-connect-btn", function () {
        $(this).text("Weiterleitung…").prop("disabled", true);
        frappe.call({
            method: "diakronos.kronos.api.google_import.get_oauth_url",
            callback: function (r) {
                if (r.message && r.message.url) {
                    window.location.href = r.message.url;
                } else {
                    frappe.msgprint("Fehler beim Erstellen der OAuth-URL.");
                }
            },
        });
    });
}


function loadStep3(wrapper) {
    $("#gki-step-area").html('<div class="gki-loading">Google Kalender werden geladen…</div>');

    frappe.call({
        method: "diakronos.kronos.api.google_import.get_google_calendars",
        callback: function (r) {
            const calendars = r.message || [];
            renderStep3(wrapper, calendars);
        },
        error: function (err) {
            const msg = (err && err.responseJSON && err.responseJSON._error_message) || "Unbekannter Fehler";
            $("#gki-step-area").html(`
<div class="gki-step-card">
    <p style="color:#b71c1c">Fehler beim Laden der Google Kalender: ${frappe.utils.escape_html(msg)}</p>
    <p>Bitte prüfe ob der OAuth-Token noch gültig ist und starte den Verbindungs-Flow erneut.</p>
    <button class="gki-btn gki-btn--secondary" id="gki-reauth-btn">Erneut verbinden</button>
</div>`);
            $(wrapper).on("click", "#gki-reauth-btn", function () {
                frappe.call({
                    method: "diakronos.kronos.api.google_import.save_credentials",
                    args: { client_id: "", client_secret: "" },
                    callback: function () { loadStatus(wrapper); }
                });
            });
        },
    });
}


function renderStep3(wrapper, calendars) {
    if (!calendars.length) {
        $("#gki-step-area").html('<div class="gki-step-card"><p>Keine Kalender in diesem Google-Account gefunden.</p></div>');
        return;
    }

    let calItems = "";
    calendars.forEach((cal, idx) => {
        const primaryBadge = cal.primary ? '<span class="gki-cal-badge">Haupt</span>' : "";
        calItems += `
<div class="gki-cal-item" data-idx="${idx}" data-google-id="${frappe.utils.escape_html(cal.id)}" data-google-name="${frappe.utils.escape_html(cal.summary)}">
    <input type="checkbox" class="gki-cal-checkbox" checked>
    <div class="gki-cal-info">
        <div class="gki-cal-name">${frappe.utils.escape_html(cal.summary)}${primaryBadge}</div>
    </div>
    <div class="gki-cal-dot" style="background:${frappe.utils.escape_html(cal.backgroundColor || '#4285F4')}"></div>
    <div class="gki-cal-target">
        <select class="gki-cal-select" data-color="${frappe.utils.escape_html(cal.backgroundColor || '#4285F4')}">
            <option value="__new__">Neuen Kalender anlegen</option>
        </select>
        <select class="gki-cal-timefilter" title="Welche Termine importieren?">
            <option value="all">Alle Termine</option>
            <option value="from_today">Ab heute</option>
            <option value="last_year">Letztes Jahr</option>
            <option value="last_3_years">Letzte 3 Jahre</option>
        </select>
    </div>
</div>`;
    });

    const html = `
<div class="gki-step-card gki-step-done">
    <div class="gki-step-title"><span class="gki-step-num">✓</span> Mit Google verbunden</div>
    <p class="gki-step-desc" style="margin:0">
        <a href="#" id="gki-reauth-link">Anderen Account verwenden</a>
    </p>
</div>

<div class="gki-step-card">
    <div class="gki-step-title">
        <span class="gki-step-num">3</span>
        Kalender auswählen und importieren
    </div>
    <p class="gki-step-desc">
        Wähle welche Kalender importiert werden sollen. Du kannst jeden Kalender einem bestehenden Frappe-Kalender zuordnen oder einen neuen anlegen lassen.
    </p>
    <div class="gki-cal-list" id="gki-cal-list">
        ${calItems}
    </div>
    <div class="gki-btn-row">
        <button class="gki-btn gki-btn--primary" id="gki-import-btn">Ausgewählte importieren</button>
        <button class="gki-btn gki-btn--secondary" id="gki-select-all-btn">Alle auswählen</button>
        <button class="gki-btn gki-btn--secondary" id="gki-deselect-all-btn">Alle abwählen</button>
    </div>
    <div id="gki-progress" class="gki-hidden">
        <div class="gki-progress-row">
            <div class="gki-progress-spinner"></div>
            <div class="gki-progress-text">
                <div>Kalender: <strong id="gki-prog-cal">–</strong> <span id="gki-prog-num" style="color:#999"></span></div>
                <div>Termine importiert: <strong id="gki-prog-count">0</strong></div>
            </div>
        </div>
    </div>
    <div id="gki-google-result" class="gki-result gki-hidden"></div>
</div>`;

    $("#gki-step-area").html(html);

    // Bestehende Frappe-Kalender in Selects laden
    frappe.db.get_list("Kalender", {fields: ["name"], limit: 200}).then(list => {
        $(".gki-cal-select").each(function () {
            list.forEach(k => {
                $(this).append(`<option value="${frappe.utils.escape_html(k.name)}">${frappe.utils.escape_html(k.name)}</option>`);
            });
        });
    });

    // Reauth
    $(wrapper).on("click", "#gki-reauth-link", function (e) {
        e.preventDefault();
        renderStep2(wrapper);
    });

    // Alle/Keine auswählen
    $(wrapper).on("click", "#gki-select-all-btn", function () {
        $(".gki-cal-checkbox").prop("checked", true);
    });
    $(wrapper).on("click", "#gki-deselect-all-btn", function () {
        $(".gki-cal-checkbox").prop("checked", false);
    });

    // Import starten
    $(wrapper).on("click", "#gki-import-btn", function () {
        handleGoogleImport(wrapper);
    });
}


// ── Import-Handler ──────────────────────────────────────────────────────────

function handleGoogleImport(wrapper) {
    const mappings = [];
    $("#gki-cal-list .gki-cal-item").each(function () {
        if (!$(this).find(".gki-cal-checkbox").is(":checked")) return;
        const select = $(this).find(".gki-cal-select");
        const target = select.val();
        mappings.push({
            google_id:       $(this).data("google-id"),
            google_name:     $(this).data("google-name"),
            target_kalender: target === "__new__" ? "" : target,
            create_new:      target === "__new__",
            color:           select.data("color"),
            time_filter:     $(this).find(".gki-cal-timefilter").val() || "all",
        });
    });

    if (!mappings.length) {
        frappe.msgprint("Bitte mindestens einen Kalender auswählen.");
        return;
    }

    const btn      = $("#gki-import-btn");
    const progDiv  = $("#gki-progress");
    const resDiv   = $("#gki-google-result");

    btn.text("Import läuft…").prop("disabled", true);
    resDiv.addClass("gki-hidden");
    progDiv.removeClass("gki-hidden");
    $("#gki-prog-cal").text("–");
    $("#gki-prog-count").text("0");
    $("#gki-prog-num").text("");

    function _finish() {
        frappe.realtime.off("gcal_import_progress");
        progDiv.addClass("gki-hidden");
        btn.text("Ausgewählte importieren").prop("disabled", false);
    }

    // Realtime-Listener für Fortschritt
    frappe.realtime.on("gcal_import_progress", function (data) {
        if (data.status === "starting" || data.status === "importing") {
            if (data.calendar_name) $("#gki-prog-cal").text(data.calendar_name);
            if (data.cal_num)       $("#gki-prog-num").text(`(${data.cal_num}/${data.cal_total})`);
            if (typeof data.imported === "number") $("#gki-prog-count").text(data.imported);
        }
        if (data.status === "warning" && data.warning) {
            frappe.show_alert({ message: "⚠ " + data.warning, indicator: "orange" }, 12);
        }
        if (data.status === "error" && data.error) {
            frappe.show_alert({ message: "⚠ " + data.error, indicator: "red" }, 8);
        }
        if (data.status === "done") {
            _finish();
            if (data.error) {
                resDiv.removeClass("gki-hidden gki-result--success").addClass("gki-result--error")
                    .html(`<div class="gki-result-title">❌ Import fehlgeschlagen</div><div class="gki-result-detail">${frappe.utils.escape_html(data.error)}</div>`);
                return;
            }
            let detail = `<strong>${data.total_imported || 0}</strong> Termine importiert, <strong>${data.total_skipped || 0}</strong> übersprungen.<br><br>`;
            (data.calendars || []).forEach(c => {
                detail += `📅 <strong>${frappe.utils.escape_html(c.google_name)}</strong> → ${frappe.utils.escape_html(c.frappe_kalender)}: ${c.imported} importiert, ${c.skipped} übersprungen<br>`;
            });
            resDiv.removeClass("gki-hidden gki-result--error").addClass("gki-result--success")
                .html(`<div class="gki-result-title">✅ Import abgeschlossen</div><div class="gki-result-detail">${detail}</div>`);
        }
    });

    // Import in Hintergrundwarteschlange stellen
    frappe.call({
        method: "diakronos.kronos.api.google_import.start_import",
        args: { mappings_json: JSON.stringify(mappings) },
        callback: function (r) {
            if (!r.message || !r.message.queued) {
                _finish();
                frappe.show_alert({ message: "Import konnte nicht gestartet werden.", indicator: "red" }, 8);
            }
            // Sonst warten wir auf das Realtime-Event "done"
        },
        error: function (err) {
            _finish();
            const msg = (err && err.responseJSON && err.responseJSON._error_message) || "Unbekannter Fehler";
            frappe.show_alert({ message: "❌ " + msg, indicator: "red" }, 10);
        },
    });
}


function handleIcalImport(wrapper) {
    const fileInput = document.getElementById("ical-file-input");
    if (!fileInput || !fileInput.files.length) {
        frappe.msgprint("Bitte zuerst eine .ics-Datei auswählen.");
        return;
    }

    const mode = $("input[name='ical_mode']:checked").val();
    const create_new = mode === "new";
    let target_kalender = "";
    let calendar_name_new = "";
    let color = "#4285F4";

    if (create_new) {
        calendar_name_new = $("#ical-cal-name").val().trim();
        color = $("#ical-cal-color").val();
        if (!calendar_name_new) {
            frappe.msgprint("Bitte einen Namen für den neuen Kalender eingeben.");
            return;
        }
    } else {
        target_kalender = $("#ical-existing-select").val();
        if (!target_kalender) {
            frappe.msgprint("Bitte einen Ziel-Kalender auswählen.");
            return;
        }
    }

    const reader = new FileReader();
    reader.onload = function (e) {
        const raw = e.target.result;
        const b64 = btoa(unescape(encodeURIComponent(raw)));

        const btn = document.getElementById("ical-import-btn");
        btn.textContent = "Import läuft…";
        btn.disabled = true;
        $("#ical-result").addClass("gki-hidden");

        frappe.call({
            method: "diakronos.kronos.api.google_import.upload_ical",
            args: {
                file_content_b64: b64,
                target_kalender,
                create_new: create_new ? 1 : 0,
                color,
                calendar_name_new,
            },
            timeout: 120,
            callback: function (r) {
                btn.textContent = "Kalender importieren";
                btn.disabled = false;
                const res = r.message || {};
                const detail = `<strong>${res.imported || 0}</strong> Termine importiert, <strong>${res.skipped || 0}</strong> übersprungen.<br>Kalender: <strong>${frappe.utils.escape_html(res.kalender || "")}</strong>`;
                $("#ical-result")
                    .removeClass("gki-hidden gki-result--error")
                    .addClass("gki-result--success")
                    .html(`<div class="gki-result-title">✅ Import abgeschlossen</div><div class="gki-result-detail">${detail}</div>`);
            },
            error: function (err) {
                btn.textContent = "Kalender importieren";
                btn.disabled = false;
                const msg = (err && err.responseJSON && err.responseJSON._error_message) || "Unbekannter Fehler";
                $("#ical-result")
                    .removeClass("gki-hidden gki-result--success")
                    .addClass("gki-result--error")
                    .html(`<div class="gki-result-title">❌ Fehler</div><div class="gki-result-detail">${frappe.utils.escape_html(msg)}</div>`);
            },
        });
    };
    reader.readAsText(fileInput.files[0]);
}


function loadExistingKalender() {
    const sel = document.getElementById("ical-existing-select");
    if (sel.options.length > 1) return;  // schon geladen
    frappe.db.get_list("Kalender", {fields: ["name"], limit: 200}).then(list => {
        list.forEach(k => {
            const opt = document.createElement("option");
            opt.value = k.name;
            opt.textContent = k.name;
            sel.appendChild(opt);
        });
    });
}
