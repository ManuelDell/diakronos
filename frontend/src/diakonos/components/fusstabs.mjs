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
import { modulChatErlaubt as modulChatErlaubtRouter } from '../modulRechte.mjs'

/** Feste Fußzeilen-Tabs. `seiten` ordnet den aktiven Zustand zu.
 *  CHAT-R2a (Chat-Konzept 10.1 Punkt 1, 10.2, Entscheidung Manuel 17.11.):
 *  Die Leiste ist **Start · Nachrichten · Gruppen · Kalender** — „Personen“
 *  war ein Platz und ist durch „Nachrichten“ ersetzt (dieselbe Zahl von
 *  Plätzen, N5). Der fünfte Platz „Mehr“ ist KEIN eigener Tab: der Menü-Knopf
 *  oben links öffnet die Schublade (UX3e), und dort steht auch
 *  „Einstellungen“ mit der umgezogenen Personenverwaltung — so beschreibt es
 *  der Entwurf A-handy.html und Abschnitt 10.2 des Konzepts.
 *  Die bisherigen Ziele „Dienste“, „Beiträge“ und „Wiki“ bleiben in der
 *  Schublade erreichbar (die Schublade zeigt die volle Seitenleiste).
 *
 *  Rechte (CHAT-R2a-2, Punkt b): Die Leiste zeigt nur, was diese Sitzung
 *  öffnen darf. `nurMitglied` blendet Ziele für Gäste aus, `istAdmin`/`module`
 *  reichen die Rechte der Sitzung an die Modul-Prüfung. Vorher stand
 *  „Nachrichten“ fest in der Leiste, der Router-Guard schickte den Klick dann
 *  auf den Start zurück: eine Sackgasse.
 *
 *  Die Modul-Regel ist NICHT hier nachgebaut: sie steht in `modulRechte.mjs`
 *  (DOM-frei) und wird vom Router-Guard, von der Leiste und vom Menü geteilt —
 *  dieselbe Funktion, damit Leiste und Wächter nie auseinanderlaufen:
 *  Administrator immer, sonst nur mit einer Modulliste, die `chat` enthält;
 *  fehlt die Liste (`null`), bleibt der Tab weg (fail closed). Statt
 *  `window.__DIakonosBOOT` nimmt `fusstabs()` die beiden Felder als Wert
 *  (`istAdmin`, `module`) — so ist die Regel ohne DOM prüfbar, im Betrieb sind
 *  es dieselben Felder des Boot-Objekts. */
export const FUSSTAB_TABS = [
    { href: '#/',            label: 'Start',       icon: 'home',   seiten: ['Home'] },
    // CHAT-R2a: „Nachrichten“ trägt die Seiten des Chat-Bereichs — der Chat
    // selbst (`Nachrichten`), ein geöffnetes Gespräch (`Nachrichten`) und die
    // Trefferliste der Suche. Ein Zähler ungelesener Nachrichten liegt seit
    // CHAT-3a HIER (`badge: 'nachrichten'`, gespeist aus `meine_gespraeche`),
    // nicht zusätzlich in der Glocke.
    // CHAT-R2a-2: `modul: 'chat'` — ohne das Modul kein Tab (fail closed,
    // dieselbe Regel wie der Router-Guard `modulChatErlaubt`, s. o.).
    { href: '#/nachrichten', label: 'Nachrichten', icon: 'nachricht', seiten: ['Nachrichten'], nurMitglied: true, modul: 'chat', badge: 'nachrichten' },
    { href: '#/gruppen',     label: 'Gruppen',     icon: 'layout-grid', seiten: ['GruppenBereich', 'GruppeDetail'], nurMitglied: true },
    { href: '#/kalender',    label: 'Kalender',    icon: 'calendar', seiten: ['Kalender', 'KalenderImport', 'KalenderVerwaltung', 'Pruefen', 'Moderation'] },
    // CHAT-3a (Chat-Konzept 10.1/10.2, von Manuel am 17.11. mit den Entwürfen
    // freigegeben): der FÜNFTE Platz heißt „Mehr“. Er ist die alte
    // Menü-Schublade (UX3e, `AppMenueSchublade.vue`) — KEIN fünfter Seitenbaum,
    // kein eigenes Blatt: die Schublade zeigt weiter die VOLLE Seitenleiste
    // samt Fuß (Einstellungen → Personenverwaltung, Profil, Abmelden).
    // Damit löst diese Karte die Regel „kein Mehr in der Leiste“ vom 03.11. ab
    // (`tests/ux3e-handy-navigation.test.mjs` ist entsprechend angepasst).
    // `schublade: true` sagt dem Zeichner: dieser Eintrag ist ein KNOPF, kein
    // Link — er hat keine Seite, sondern öffnet das Menü.
    // Das Symbol ist die DREI-PUNKTE-Reihe (`ICON_PFADE.mehr`, dieselbe
    // Strichfamilie) — ein Zahnrad stand für „Einstellungen“ (Review R1).
    { href: '', label: 'Mehr', icon: 'mehr', seiten: [], schublade: true },
]

/**
 * Darf diese Sitzung einen Tab mit Modul öffnen? Die EINE Fassung der Regel
 * steht in `modulRechte.mjs` (dieselbe, die der Router-Guard benutzt) — hier
 * wird sie nur mit den durchgereichten Werten aufgerufen, kein zweiter Nachbau.
 *
 * @param {{modul?: string}} tab
 * @param {{istAdmin?: boolean, module?: string[]|null}} rechte
 */
export function tabErlaubt(tab, { istAdmin = false, module = null } = {}) {
    if (!tab || !tab.modul) return true
    return modulChatErlaubtRouter({
        is_admin: istAdmin === true,
        module_sichtbar: Array.isArray(module) ? module : null,
    })
}

/** Die `badge`-Quellen, die die Leiste kennt (EINE Liste, damit ein Tippfehler
 *  in `FUSSTAB_TABS` nicht stillschweigend einen leeren Zähler ergibt). */
export const ZAEHLER_QUELLEN = ['nachrichten']

/**
 * Die Zahl, die ein Tab als Zähler trägt.
 *
 * `zaehler` ist die eine Zahl der Seite (`ungelesenSumme` der Gespräche,
 * `null` solange nichts geladen ist). Eine zweite Abfrage gibt es nicht —
 * dieselbe Zahl steht in der Schublade und in der Seitenleiste.
 *
 * @param {{badge?: string}} tab
 * @param {{nachrichten?: number|null}} zaehler
 * @returns {string} '' = kein Zähler
 */
export function tabZaehler(tab, zaehler = {}) {
    const quelle = tab && tab.badge
    if (!quelle || !ZAEHLER_QUELLEN.includes(quelle)) return ''
    const wert = Number(zaehler?.[quelle])
    if (!Number.isFinite(wert) || wert <= 0) return ''
    // Ab 100 wird gekappt: eine dreistellige Zahl sprengt den Tab am Handy.
    return wert > 99 ? '99+' : String(wert)
}

/**
 * Sichtbare Fußzeilen-Tabs.
 *
 * @param {{istGast?: boolean, istAdmin?: boolean, module?: string[]|null, boot?: object}} rechte
 *        `module` überschreibt die Modulliste der Sitzung (Tests/Aufrufer, die
 *        sie schon kennen); ohne Angabe gilt `boot.module_sichtbar` bzw.
 *        `window.__DIakonosBOOT.module_sichtbar`.
 *        `istAdmin` überschreibt `is_admin` — genau wie bei der Modulliste,
 *        damit Test und Laufzeit dieselbe Quelle benutzen.
 */
export function fusstabs({ istGast = false, istAdmin, module, boot } = {}) {
    const quelle = boot || (typeof window === 'undefined' ? {} : (window.__DIakonosBOOT || {}))
    const meineModule = module === undefined
        ? (Array.isArray(quelle.module_sichtbar) ? quelle.module_sichtbar : null)
        : (Array.isArray(module) ? module : null)
    const ichBinAdmin = istAdmin === undefined ? quelle.is_admin === true : istAdmin === true
    return FUSSTAB_TABS.filter(t => {
        if (t.nurMitglied && istGast) return false
        // R-3/CHAT-R2a-2: der Tab hängt am Modul — dieselbe Prüfung wie der
        // Router-Guard, also NICHT fail open: fehlt die Modulliste, verschwindet
        // der Tab (sonst führte er in eine Sackgasse, aus der der Wächter auf
        // den Start zurückwirft).
        if (!tabErlaubt(t, { istAdmin: ichBinAdmin, module: meineModule })) return false
        return true
    })
}
