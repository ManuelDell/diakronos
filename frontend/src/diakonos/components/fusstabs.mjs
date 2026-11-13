/**
 * p2-3 · Fußzeilen-Tabs der Handy-Navigation (DES-R9, OP-HANDY-15, OP-ADMIN-21).
 *
 * Die vier festen Tabs der unteren Leiste standen als feste <a>-Elemente in
 * AppBottomNav.vue und widersprachen der übrigen Handy-Navigation sowie der
 * Seitenleiste:
 *   * DES-R9/OP-ADMIN-21 — Desktop und Handy zeigten verschiedene Seiten,
 *   * OP-HANDY-15 — Gästen blieb „Ressourcen“ (der Server weist sie ab).
 *
 * Diese Liste ist die eine Quelle für die festen Tabs. `istGast` blendet
 * „Ressourcen“ aus, weil der Server Gästen den Zugriff verweigert — die
 * Oberfläche lässt nur weg, was der Server ohnehin nicht erlaubt.
 */

/** Feste Fußzeilen-Tabs. `seiten` ordnet den aktiven Zustand zu.
 *  UX3a (Entwurf A8): Übersicht · Kalender · Dienste · Beiträge · Wiki — die
 *  Leiste zeigt die häufigen Ziele der Handy-Nutzung; alles andere steht in
 *  der Menü-Schublade oben links (UX3e — dieselbe Quelle, menue.js). „Dienste“
 *  öffnet die persönliche Sicht „Meine Dienste“.
 *  UX3a2: „Dienste“ ist NICHT mehr für Gäste da — UX3a hatte den Tab (wie den
 *  Menüpunkt) für Gäste geöffnet, der Bereich ist aber wie vor UX3a nur für
 *  Mitglieder (der Router sperrt ihn ebenso). Ohne `nurMitglied` bot die
 *  untere Leiste Gästen ein Ziel, das sie sofort wieder verliessen
 *  (OP-ADMIN-21: Desktop und Handy bieten dieselben Seiten). */
export const FUSSTAB_TABS = [
    { href: '#/',          label: 'Übersicht',  icon: 'home',   seiten: ['Home'] },
    { href: '#/kalender',  label: 'Kalender',   icon: 'calendar', seiten: ['Kalender', 'KalenderImport', 'KalenderVerwaltung', 'Pruefen', 'Moderation'] },
    { href: '#/dienste',   label: 'Dienste',    icon: 'clock', nurMitglied: true,
      seiten: ['Dienste', 'Dienstplan', 'DiensteDienstplaene', 'DiensteVorlagen', 'PlanrahmenUebersicht', 'PlanrahmenPlan', 'PlanrahmenEinrichten', 'PlanrahmenPlantypEditor', 'PlanrahmenStammdaten', 'PlanrahmenDienste'] },
    { href: '#/beitraege', label: 'Beiträge',   icon: 'file-text', seiten: ['Beitraege', 'BeitragDetail'], nurMitglied: true },
    { href: '#/wiki',      label: 'Wiki',       icon: 'help-circle', seiten: ['Wiki', 'WikiArtikel'], nurMitglied: true },
]

/**
 * Sichtbare Fußzeilen-Tabs.
 * @param {{istGast?: boolean}} rechte
 */
export function fusstabs({ istGast = false } = {}) {
    return FUSSTAB_TABS.filter(t => !(t.nurMitglied && istGast))
}
