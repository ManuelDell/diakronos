/**
 * ═══════════════════════════════════════════════════════════════
 * KRONOS MODAL - HELPER UTILITIES
 * ═══════════════════════════════════════════════════════════════
 * Wiederverwendbare Funktionen für alle Modal-Module
 */


class KronosModalHelpers {
    
    /**
     * 🔧 DATETIME FORMATTING
     * Konvertiert ISO-Datetime zu datetime-local Format
     */
    static formatToLocalDatetime(dateStr) {
        if (!dateStr) return '';
        const date = new Date(dateStr);
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        const hours = String(date.getHours()).padStart(2, '0');
        const minutes = String(date.getMinutes()).padStart(2, '0');
        return `${year}-${month}-${day}T${hours}:${minutes}`;
    }
    
    /**
     * 🛡️ HTML ESCAPING
     * Escape HTML-Sonderzeichen in User-Input
     */
    static escapeHtml(text) {
        if (!text) return '';
        const map = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;'
        };
        return String(text).replace(/[&<>"']/g, m => map[m]);
    }
    
    /**
     * 🔄 DATETIME CONVERSION
     * Konvertiert datetime-local zu MySQL Format (YYYY-MM-DD HH:MM:SS)
     */
    static convertToMySQLDatetime(datetimeLocalValue) {
        if (!datetimeLocalValue) return '';
        const date = new Date(datetimeLocalValue);
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        const hours = String(date.getHours()).padStart(2, '0');
        const minutes = String(date.getMinutes()).padStart(2, '0');
        const seconds = String(date.getSeconds()).padStart(2, '0');
        
        return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
    }
    
    /**
     * ✅ MODAL STYLE DEFAULTS
     * Standard CSS für alle Modals
     */
    static getModalStyle() {
        return 'position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 9999; opacity: 1; transition: opacity 0.2s ease-out;';
    }
    
    static getDialogStyle() {
        return 'background: white; border-radius: 8px; padding: 24px; box-shadow: 0 4px 12px rgba(0,0,0,0.15); animation: slideUp 0.3s ease-out;';
    }
    
    /**
     * 🎨 HOVER EFFECT HELPER
     * Fügt Hover-Effekte zu Buttons hinzu
     */
    static addHoverEffect(elementId) {
        const element = document.getElementById(elementId);
        if (!element) return;
        
        element.addEventListener('mouseenter', () => {
            element.style.transform = 'translateY(-2px)';
            element.style.boxShadow = '0 4px 8px rgba(0,0,0,0.1)';
        });
        
        element.addEventListener('mouseleave', () => {
            element.style.transform = 'translateY(0)';
            element.style.boxShadow = 'none';
        });
    }
    
    /**
     * 🔽 CLOSE MODAL HELPER
     * Standard Close-Animation
     */
    static closeModal(modalElement, callback = null) {
        console.log('🔽 Schließe Modal');
        modalElement.style.opacity = '0';
        
        setTimeout(() => {
            if (modalElement && modalElement.parentNode) {
                modalElement.remove();
            }
            if (callback) {
                callback();
            }
        }, 200);
    }
    
    /**
     * 📡 ASYNC SAVE TO FRAPPE
     * Speichert Daten via frappe.call
     */
    static async saveSingleEvent(element, updateData) {
        return new Promise((resolve, reject) => {
            const payload = {};
            
            Object.entries(updateData).forEach(([key, value]) => {
                if (key.includes('start') || key.includes('end')) {
                    payload[key] = KronosModalHelpers.convertToMySQLDatetime(value);
                } else {
                    payload[key] = value;
                }
            });
            
            console.log('📤 Final Payload:', payload);
            
            frappe.call({
                method: 'frappe.client.set_value',
                args: {
                    doctype: 'Element',
                    name: element.name,
                    fieldname: payload
                },
                callback: (r) => {
                    console.log('✅ Backend Response:', r);
                    resolve(r);
                },
                error: (err) => {
                    console.error('❌ Fehler beim Speichern:', err);
                    reject(err);
                }
            });
        });
    }
    
    /**
     * 🗑️ ASYNC DELETE
     */
    static async deleteElement(doctype, name) {
        return new Promise((resolve, reject) => {
            frappe.call({
                method: 'frappe.client.delete',
                args: { doctype, name },
                callback: resolve,
                error: reject
            });
        });
    }
    
    /**
     * 🔗 ASYNC SERIES OPERATIONS
     */
    static async removeFromSeries(elementName) {
        return new Promise((resolve, reject) => {
            frappe.call({
                method: 'frappe.client.set_value',
                args: {
                    doctype: 'Element',
                    name: elementName,
                    fieldname: { series_id: null }
                },
                callback: resolve,
                error: reject
            });
        });
    }
    
    static async deleteSeries(seriesId) {
        return new Promise((resolve, reject) => {
            frappe.call({
                method: 'diakronos.kronos.api.series_update.delete_series_batch',
                args: { series_id: seriesId },
                callback: resolve,
                error: reject
            });
        });
    }
    
    /**
     * 📢 TOAST NOTIFICATION HELPER
     */
    static showSuccess(message, title = '✅') {
        frappe.show_alert({
            message: `${title} ${message}`,
            indicator: 'green'
        });
    }
    
    static showError(message, title = '❌') {
        frappe.show_alert({
            message: `${title} ${message}`,
            indicator: 'red'
        });
    }
    
    static showWarning(message, title = '⚠️') {
        frappe.show_alert({
            message: `${title} ${message}`,
            indicator: 'orange'
        });
    }

    /**
     * 📂 DROPDOWN OPTIONS LOADER
     * Lade Kalender und Kategorien aus Frappe
     */
    static async loadDropdownOptions() {
        try {
            const response = await frappe.call({
                method: 'diakronos.kronos.doctype.element.element.get_calendar_and_category_options'
            });
            console.log('✅ Dropdown-Optionen geladen:', response.message);
            return response.message || { calendars: [], categories: [] };
        } catch (err) {
            console.error('❌ Fehler beim Laden der Optionen:', err);
            KronosModalHelpers.showError('Kalender und Kategorien konnten nicht geladen werden');
            return { calendars: [], categories: [] };
        }
    }
}


// Export
window.KronosModalHelpers = KronosModalHelpers;
console.log('✅ Modal Helpers geladen');
