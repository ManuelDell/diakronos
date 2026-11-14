/**
 * handyMenue.mjs — UX3e: Handy-Navigation „Leiste unten + Menü oben links“.
 *
 * Entwurf A8/A9 (Manuel 2026-11-03/04, freigegeben):
 *   * Die untere Leiste zeigt die fünf häufigen Ziele
 *     **Übersicht · Kalender · Dienste · Beiträge · Wiki** — KEIN „Mehr“.
 *   * Das Menü-Symbol OBEN LINKS (Kopfzeile) öffnet eine Schublade, die wie
 *     die Seitenleiste gruppiert ist: Gruppen aus `menue.js` mit Überschrift,
 *     darunter der Fußbereich (Einstellungen · Profil · Abmelden).
 *
 * Warum diese Datei existiert (und nicht alles in der Komponente steht):
 * Die Regeln „was steht in der Schublade“ und „welcher Eintrag ist aktiv“
 * sind ohne Browser prüfbar. Die Vue-Komponente (AppMenueSchublade.vue)
 * zeichnet nur. Eine zweite Fassung derselben Regel gibt es nicht.
 *
 * Kreislauf, den die Karte schließt: Der alte „Mehr“-Knopf war der EINZIGE
 * Weg zu Lieder, Website, Ressourcen, Gruppen und Einstellungen. Er entfällt
 * (Entscheidung Manuel). Damit am Handy dieselben Seiten erreichbar bleiben
 * wie am Desktop, zeigt die Schublade die VOLLSTÄNDIGE Seitenleiste — auch
 * die Ziele, die zusätzlich in der Leiste stehen (Kalender, Dienste,
 * Beiträge, Wiki). So zeigt es der freigegebene Entwurf A9: die Schublade ist
 * die Seitenleiste in Handy-Form, die Leiste nur eine Abkürzung.
 */
import { MENUE, FUSS_EINTRAEGE, sichtbareEintraege, verwaltungZutreffend } from '../menue.js'

/**
 * Einträge der Schublade in Anzeigereihenfolge — EINE Quelle für Oberfläche
 * und Test. Dieselben Gruppen, dieselbe Reihenfolge und dieselben
 * Sichtbarkeitsregeln wie die Seitenleiste (`sichtbareEintraege` aus
 * `menue.js`) — Gäste sehen also genau, was die Seitenleiste ihnen zeigt.
 *
 * @param {{istAdmin?: boolean, istTester?: boolean, istGast?: boolean,
 *          rollen?: string[]}} optionen
 * @returns {Array<{gruppe: string, eintraege: Array<object>}>}
 *   Gruppen wie in der Seitenleiste; die Gruppe ohne Namen („“) ist
 *   „Übersicht“.
 */
export function schubladeMenue({
    istAdmin = false,
    istMitgliederverwaltung = false,
    istTester = false,
    istGast = false,
    rollen = [],
} = {}) {
    return MENUE.map(gruppe => ({
        gruppe: gruppe.gruppe,
        eintraege: sichtbareEintraege(gruppe, { istAdmin, istMitgliederverwaltung, istTester, istGast, rollen }),
    })).filter(gruppe => gruppe.eintraege.length > 0)
}

/**
 * Fußbereich der Schublade — dieselbe Rollenregel wie in der Seitenleiste
 * (`FUSS_EINTRAEGE`). Er steht NICHT in der Gruppenliste, sondern getrennt
 * unter dem Strich, genau wie „Einstellungen“ am Desktop unten in der
 * Seitenleiste steht (Entwurf A1/A9).
 */
export function sichtbarerFuss({ istAdmin = false, istMitgliederverwaltung = false } = {}) {
    // UI-R10: „Einstellungen“ ist Personenbereich — die Mitgliederverwaltung
    // pflegt dort Anmeldung, Registrierung und Datenschutz (R-11a). Innerhalb
    // der Seite sind die Administrations-Abschnitte weiterhin nur für den
    // Administrator (der Server verweigert sie ohnehin mit 403).
    const rechte = { istAdmin, istMitgliederverwaltung }
    return FUSS_EINTRAEGE.filter((e) => !e.verwaltung || verwaltungZutreffend(e.verwaltung, rechte))
}

/**
 * Ist der Eintrag der aktive? Dieselbe Regel wie in der Seitenleiste
 * (AppSidebar.vue `istAktiv`), hier ohne Vue-Zustand: `seite` ist der
 * Seitenname der aktuellen Route, `hash` die aktuelle Adresse.
 *
 * „Gruppen“ gilt auch auf der Detailseite einer Gruppe (`#/gruppe/:name`),
 * deren Seitenname `GruppeDetail` lautet — sonst stünde die Schublade dort
 * ohne Markierung da, während die Seitenleiste markiert.
 */
export function istEintragAktiv(eintrag, { seite = '', hash = '' } = {}) {
    if (!eintrag || !Array.isArray(eintrag.seiten)) return false
    if (eintrag.href === '#/gruppen') {
        return String(hash).startsWith('#/gruppen') || seite === 'GruppeDetail'
    }
    return eintrag.seiten.includes(seite)
}

/**
 * Ist der Tab der aktive? Die Regel lag bisher in der Komponente (Vergleich
 * über die Seitennamenliste des Tabs); hier ist sie ohne Browser prüfbar.
 * `seite` ist der Seitenname der aktuellen Route; die Unterseiten eines
 * Bereichs (z. B. `KalenderVerwaltung`, `Moderation`) stehen in `tab.seiten`,
 * damit der Bereich dort markiert bleibt.
 */
export function istTabAktiv(tab, { seite = '' } = {}) {
    if (!tab || !Array.isArray(tab.seiten)) return false
    return tab.seiten.includes(seite)
}

/**
 * Vorlesetext des Menü-Knopfes oben links (Prinzip N8 „beschriften statt nur
 * Symbole“: das Symbol allein ist am Handy mehrdeutig).
 */
export const MENUE_KNOPF_TEXT = 'Menü'

/** Sichtbare Beschriftung des Schubladenkopfes. */
export const SCHUBLADE_KOPF_TEXT = 'Menü'

/** Vorlesetext des Schließen-Knopfes im Schubladenkopf. */
export const SCHUBLADE_SCHLIESSEN_TEXT = 'Menü schließen'
