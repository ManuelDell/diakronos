/**
 * HTML Security Utilities
 * Verhindert XSS und CSS Injection in Template-Literals.
 */

/**
 * Escaped Sonderzeichen für sichere Verwendung in HTML-Attributen und -Inhalten.
 * @param {*} str
 * @returns {string}
 */
function escHtml(str) {
    return String(str == null ? '' : str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

/**
 * Validiert einen CSS-Farbwert als Hex-String.
 * Gibt den Fallback zurück wenn der Wert kein gültiger Hex-Farbwert ist.
 * @param {string} val
 * @param {string} fallback
 * @returns {string}
 */
function safeCssColor(val, fallback = 'var(--primary)') {
    if (typeof val === 'string' && /^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/.test(val.trim())) {
        return val.trim();
    }
    return fallback;
}

export { escHtml, safeCssColor };
