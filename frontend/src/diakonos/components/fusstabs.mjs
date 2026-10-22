/**
 * p2-3 · Fußzeilen-Tabs der Handy-Navigation (DES-R9, OP-HANDY-15, OP-ADMIN-21).
 *
 * Die vier festen Tabs der unteren Leiste standen als feste <a>-Elemente in
 * AppBottomNav.vue und widersprachen dem „Mehr“-Blatt sowie der Seitenleiste:
 *   * DES-R9/OP-ADMIN-21 — Desktop und Handy zeigten verschiedene Seiten,
 *   * OP-HANDY-15 — Gästen blieb „Ressourcen“ (der Server weist sie ab) und
 *     ein leeres „Mehr“-Blatt.
 *
 * Diese Liste ist die eine Quelle für die festen Tabs. `istGast` blendet
 * „Ressourcen“ aus, weil der Server Gästen den Zugriff verweigert — die
 * Oberfläche lässt nur weg, was der Server ohnehin nicht erlaubt.
 */

/** Feste Fußzeilen-Tabs. `seiten` ordnet den aktiven Zustand zu. */
export const FUSSTAB_TABS = [
    { href: '#/',          label: 'Übersicht',  icon: 'home',   seiten: ['Home'] },
    { href: '#/kalender',  label: 'Kalender',   icon: 'calendar', seiten: ['Kalender', 'KalenderImport'] },
    { href: '#/ressourcen', label: 'Ressourcen', icon: 'box',   seiten: ['Ressourcen'], nurMitglied: true },
    { href: '#/profile',   label: 'Profil',     avatar: true,   seiten: ['Profile'] },
]

/**
 * Sichtbare Fußzeilen-Tabs.
 * @param {{istGast?: boolean}} rechte
 */
export function fusstabs({ istGast = false } = {}) {
    return FUSSTAB_TABS.filter(t => !(t.nurMitglied && istGast))
}
