/**
 * API-Layer für die Terminmoderation (Kronos Kanban Board).
 * Alle Endpunkte sind @frappe.whitelist in kronos/api/kanban_api.py.
 * Nutzt apiCall() aus composables/useApi.js (kein frappe.call).
 */

import { apiCall } from '../composables/useApi.js'

const PREFIX = 'diakronos.kronos.api.kanban_api'

/**
 * Lädt alle Board-Daten: Vorschläge, Konflikte, Staging, Notifications.
 * @returns {{ vorschlaege: Array, konflikte: Array, staging: Array, notifications: Object }}
 */
export async function getBoardData() {
  return apiCall(`${PREFIX}.get_kanban_board_data`)
}

/**
 * Speichert die aktuelle Staging-Reihenfolge (debounced, 500ms).
 * @param {string[]} stagingIds — Geordnete Liste der Event-IDs
 */
export async function saveStagingState(stagingIds) {
  return apiCall(`${PREFIX}.save_staging_state`, {
    staging_ids: JSON.stringify(stagingIds),
  })
}

/**
 * Finalisiert alle gestagten Events (Status → "Festgelegt").
 * @param {string[]} eventIds
 * @returns {{ finalized: number }}
 */
export async function finalizeStagedEvents(eventIds) {
  return apiCall(`${PREFIX}.finalize_staged_events`, {
    event_ids: JSON.stringify(eventIds),
  })
}

/**
 * Holt den Konfliktpartner eines Elements (Ressourcen-Überschneidung).
 * @param {string} elementId
 * @returns {Object|null} Partner-Objekt mit title, start, end, calendar, ressource
 */
export async function getConflictPartner(elementId) {
  return apiCall(`${PREFIX}.get_conflict_partner`, {
    element_id: elementId,
  })
}

/**
 * Löst einen Konflikt auf oder entscheidet über einen Vorschlag.
 * @param {string} elementId
 * @param {'ignore'|'vorschlag'|'festlegen'|'ablehnen'} action
 * @param {Object} [edits] — Optionale Formularfelder (title, element_start, element_end, all_day, ressource, description, grund)
 * @returns {{ id: string, new_status: string, action: string }}
 */
export async function resolveConflict(elementId, action, edits = {}) {
  return apiCall(`${PREFIX}.resolve_conflict`, {
    element_id: elementId,
    action,
    ...edits,
  })
}

/**
 * Gibt die Anzahl der zu moderierenden Termine zurück.
 * @returns {{ count: number }}
 */
export async function getModerationCount() {
  return apiCall(`${PREFIX}.get_moderation_count`)
}

/**
 * Holt verfügbare Ressourcen (Räume) für die Edit-Formulare.
 * @returns {Array<{ id: string, title: string }>}
 */
export async function getRessources() {
  return apiCall('diakronos.kronos.api.ressource_api.get_ressources')
}

/**
 * Aktualisiert den Titel einer ganzen Serie.
 * @param {string} seriesId
 * @param {string} title
 */
export async function updateSeriesBatchFast(seriesId, title) {
  return apiCall('diakronos.kronos.api.series.update_series_batch_fast', {
    series_id: seriesId,
    updates: { element_name: title },
  })
}

/**
 * Löscht eine komplette Serie.
 * @param {string} seriesId
 */
export async function deleteSeriesBatchFast(seriesId) {
  return apiCall('diakronos.kronos.api.series.delete_series_batch_fast', {
    series_id: seriesId,
  })
}
