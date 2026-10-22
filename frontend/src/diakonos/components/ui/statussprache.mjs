/**
 * STATUSSPRACHE — zentrale Quelle für Status-Wort und -Kennzeichen.
 *
 * Problem gelöst: „Entwurf", „Veröffentlicht", „Warnung", „Fehler" und
 * „Hinweis" wurden bisher an jeder Stelle neu erfunden (Wortwahl + Farbe
 * wichen ab). Hier stehen Wort und Kennzeichen EINMAL beisammen; alle Seiten
 * und Komponenten verwenden `statusSprache(...)` bzw. `stufeSprache(...)`.
 *
 * Badge-Varianten entsprechen DkBadge: neutral | ok | warn | err | info | akzent.
 */

/** Planstatus (plan.status) → { wort, variant }. */
export const PLAN_STATUS = {
    entwurf:        { wort: 'Entwurf',        variant: 'warn' },
    veroeffentlicht:{ wort: 'Veröffentlicht', variant: 'ok' },
    archiviert:     { wort: 'Archiviert',     variant: 'neutral' },
}

/** Prüf-/Melde-Stufe (m.stufe oder m.art) → { wort, variant, piktogramm }. */
export const STUFEN = {
    fehler:  { wort: 'Fehler',   variant: 'err',  piktogramm: '⛔' },
    muss:    { wort: 'Fehler',   variant: 'err',  piktogramm: '⛔' },
    warnung: { wort: 'Warnung',  variant: 'warn', piktogramm: '⚠️' },
    sollte:  { wort: 'Warnung',  variant: 'warn', piktogramm: '⚠️' },
    hinweis: { wort: 'Hinweis',  variant: 'info', piktogramm: 'ℹ️' },
}

const UNBEKANNT = { wort: 'Unbekannt', variant: 'neutral', piktogramm: '•' }

/**
 * Planstatus in Klartext + Kennzeichen.
 * @param {string} status  z. B. 'entwurf', 'veroeffentlicht'
 */
export function statusSprache(status) {
    const treffer = PLAN_STATUS[String(status || '').toLowerCase()]
    return treffer
        ? { wort: treffer.wort, variant: treffer.variant }
        : { wort: 'Unbekannt', variant: 'neutral' }
}

/**
 * Prüf-/Meldestufe in Klartext + Kennzeichen + Piktogramm.
 * @param {string} stufe  z. B. 'muss', 'sollte', 'hinweis', 'fehler'
 */
export function stufeSprache(stufe) {
    return STUFEN[String(stufe || '').toLowerCase()] || UNBEKANNT
}

/** Nur das Wort eines Status (Kurzform für Vorlagen). */
export function statusWort(status) {
    return statusSprache(status).wort
}

/** Nur das Wort einer Stufe (Kurzform für Vorlagen). */
export function stufeWort(stufe) {
    return stufeSprache(stufe).wort
}

/** DkBadge-Variante → Klasse der globalen .dk-badge-Regeln (index.css). */
const BADGE_KLASSE = {
    neutral: 'dk-badge',
    ok: 'dk-badge dk-badge-success',
    warn: 'dk-badge dk-badge-warning',
    err: 'dk-badge dk-badge-danger',
    info: 'dk-badge dk-badge-info',
    akzent: 'dk-badge dk-badge-brand',
}

/** Klassenliste für ein Kennzeichen zu einem Status. */
export function statusBadgeKlasse(status) {
    return BADGE_KLASSE[statusSprache(status).variant] || BADGE_KLASSE.neutral
}

/** Klassenliste für ein Kennzeichen zu einer Prüf-Stufe. */
export function stufeBadgeKlasse(stufe) {
    return BADGE_KLASSE[stufeSprache(stufe).variant] || BADGE_KLASSE.neutral
}
