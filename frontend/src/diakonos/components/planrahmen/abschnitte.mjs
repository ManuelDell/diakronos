/**
 * UX-C3a — Sprungleiste und Erklärspalte des Plantyp-Editors.
 *
 * Die Seite ist sehr lang (Befund: ~8700 px). Statt zu scrollen springt man
 * über die Abschnittsliste; die Spalte „Was bedeutet das?“ erklärt die
 * Begriffe dauerhaft, damit keine Info-Symbole nötig sind (Entwurf C3,
 * Manuel 2026-10-23).
 *
 * Hier steht NUR die reine Logik (ohne DOM), damit sie ohne Browser prüfbar
 * ist:
 *
 *   * ABSCHNITTE — die Sprungziele in der Reihenfolge der Seite, mit den
 *     Kennungen des Markups (`data-abschnitt`) und den Zählern.
 *   * ERKLAERUNGEN — die Begriffe der Erklärspalte. Jeder Eintrag nennt
 *     seine Quelle aus der vorhandenen Doku (`doku/LEITFADEN.md`,
 *     `doku/REFERENZ.md`, `doku/GLOSSAR.md`); erfunden ist nichts.
 *   * aktiverAbschnitt() — welche Zeile beim Scrollen gilt (die letzte
 *     Überschrift, die die Lesekante erreicht hat).
 *   * erklaerungenFuer() — die Begriffe, die zu einem Abschnitt gehören
 *     (die Spalte zeigt sie zuerst, den Rest darunter).
 *   * erklaerungFehlt() — Begriffe ohne Erklärung (dann steht ein Platzhalter).
 */

/** Kennung des Abschnitts „Grunddaten“ — beim Öffnen immer der erste. */
export const ERSTER_ABSCHNITT = 'grunddaten'

/**
 * Sprungziele in der Reihenfolge der Seite.
 *
 * `zaehler` nennt den Pfad in der Definition, dessen Länge als Zahl neben dem
 * Eintrag steht (nur wo eine Zahl etwas aussagt — Grunddaten und Termine
 * tragen keine).
 */
export const ABSCHNITTE = [
    { id: 'grunddaten', name: 'Grunddaten', erklaerung: ['kennung', 'anzeigename', 'dienstbereich', 'personenpool'] },
    { id: 'termine', name: 'Termine', erklaerung: ['terminreihe', 'feld'] },
    { id: 'felder', name: 'Felder', zaehler: 'felder', erklaerung: ['feld', 'feldart'] },
    { id: 'anlaesse', name: 'Anlässe', zaehler: 'anlaesse', erklaerung: ['anlass', 'wirkung'] },
    { id: 'regeln', name: 'Regeln', zaehler: 'regeln', erklaerung: ['regel', 'stufe'] },
    { id: 'ansichten', name: 'Ansichten', zaehler: 'ansichten', erklaerung: ['ansicht', 'formatvorlage'] },
]

/**
 * Begriffserklärungen der Spalte „Was bedeutet das?“.
 *
 * `quelle` ist die Stelle in `backend/src/diakronos_app/planrahmen/doku/`,
 * aus der die Erklärung abgeleitet ist — sie steht im Werkzeugtip des
 * Begriffs, damit die Herkunft nachprüfbar bleibt.
 */
export const ERKLAERUNGEN = [
    {
        id: 'planvorlage',
        begriff: 'Planvorlage',
        text: 'Die wiederverwendbare Vorlage eines Plans. Sie legt fest, welche Termine es gibt und was pro Termin geplant wird.',
        quelle: 'GLOSSAR.md (Begriffe)',
    },
    {
        id: 'kennung',
        begriff: 'Kennung',
        text: 'Stabiler Kurzname der Vorlage (Kleinbuchstaben, Ziffern, _ und -). Sie steht in jeder Referenz und bleibt über alle Versionen gleich; der Anzeigename darf sich ändern.',
        quelle: 'REFERENZ.md:11 (`id`) · GLOSSAR.md (Kennungen)',
    },
    {
        id: 'anzeigename',
        begriff: 'Anzeigename',
        text: 'Der Name, den Planer sehen („Chorplan“). Frei wählbar — anders als die Kennung darf er sich jederzeit ändern.',
        quelle: 'REFERENZ.md:14 (`name`) · GLOSSAR.md (Kennungen)',
    },
    {
        id: 'dienstbereich',
        begriff: 'Dienstbereich',
        text: 'Ordnet die Vorlage einem Bereich der Gemeinde zu. Ein Bereich, den es in der Gemeinde nicht gibt, wird beim Speichern als Fehler gemeldet.',
        quelle: 'LEITFADEN.md B1 · Prüfung beim Speichern (dienste.py)',
    },
    {
        id: 'personenpool',
        begriff: 'Personenpool',
        text: 'Die Gruppen, aus denen eingeplant werden darf. Ohne Auswahl gilt: alle Personen. Mit Auswahl sehen die Planer nur die Mitglieder dieser Gruppen.',
        quelle: 'REFERENZ.md:27 (`gruppen`)',
    },
    {
        id: 'terminreihe',
        begriff: 'Terminreihe',
        text: 'Eine Zeitachse des Plans. Die Quelle bestimmt, woher die Termine kommen: Regel (z. B. jeder Sonntag), Zeitraum, Kalender, Feiertage, von Hand oder abgeleitet aus einer anderen Reihe.',
        quelle: 'LEITFADEN.md B2 (Termine)',
    },
    {
        id: 'feld',
        begriff: 'Feld',
        text: 'Was pro Termin geplant wird — eine Person in einer Rolle, ein Eintrag aus einer Sammlung (Lied), ein Text, eine Zahl oder eine Gruppe mit Unterfeldern.',
        quelle: 'LEITFADEN.md B3 (Felder)',
    },
    {
        id: 'feldart',
        begriff: 'Feldart',
        text: 'Bestimmt, wer den Wert setzt: person, personen, eintrag und team teilt der Planer automatisch ein, alles andere füllt er von Hand — außer das Feld schreibt eine andere Füllstrategie vor.',
        quelle: 'LEITFADEN.md B3 · B7 (Füllstrategien)',
    },
    {
        id: 'anlass',
        begriff: 'Anlass',
        text: 'Eine Markierung an einzelnen Terminen (Abendmahl, Kinderchor, Erntedank). Ein Feiertag setzt automatisch einen Anlass gleichen Namens.',
        quelle: 'LEITFADEN.md B6 (Anlässe)',
    },
    {
        id: 'wirkung',
        begriff: 'Wirkung',
        text: 'Was ein Anlass ändert: Felder ausblenden (ohne), zusätzliche Felder zeigen (mit), eigene Regeln steuern (regeln) — auch nur unter einer Bedingung.',
        quelle: 'LEITFADEN.md B6 (Anlässe)',
    },
    {
        id: 'regel',
        begriff: 'Regel',
        text: 'Ein benannter Baustein mit Einstellungen, der das automatische Einteilen steuert — zum Beispiel „nicht öfter als alle 8 Wochen“ (Mindestabstand). Welche Einstellungen ein Baustein hat, gibt die Baustein-Registry vor.',
        quelle: 'LEITFADEN.md B8 (Regeln) · REFERENZ.md „Regel-Bausteine“',
    },
    {
        id: 'stufe',
        begriff: 'Stufe',
        text: 'Wie streng eine Regel gilt: muss wird nie verletzt, sollte möglichst erfüllt, hinweis ist nur ein Anzeigepunkt.',
        quelle: 'REFERENZ.md:316 (`stufe`) · LEITFADEN.md B8 (Regeln)',
    },
    {
        id: 'ansicht',
        begriff: 'Ansicht',
        text: 'Wie ein Plan dargestellt wird: Tabelle, Raster, Ablauf, meine Dienste, Druck, iCal oder Kalender. Eine Vorlage darf mehrere Ansichten haben.',
        quelle: 'LEITFADEN.md B9 (Ansichten)',
    },
    {
        id: 'formatvorlage',
        begriff: 'Formatvorlage',
        text: 'Bestimmt, was in einer Zelle steht, z. B. „{eintrag.buch} Nr.{eintrag.nummer}“. Platzhalter, die auf nichts zeigen, meldet die Prüfung als Warnung.',
        quelle: 'LEITFADEN.md B9 (Ansichten)',
    },
    // UX-C3b: Kennungen, für die es seit dieser Karte Auswahllisten gibt. Das
    // ⓘ am Feld nennt genau den Eintrag hier — dasselbe Glossar wie die
    // Erklärspalte, keine zweite Wahrheit.
    {
        id: 'sammlung',
        begriff: 'Liste / Sammlung',
        text: 'Eine benannte Liste, aus der ein Eintrag-Feld wählt („lieder“ ist eingebaut, eigene Listen stehen unter Deklarationen). Der Name ist eine feste Kennung — deshalb ein Auswahlfeld. Ein Wert, den es nicht mehr gibt, bleibt sichtbar, bis du ihn ersetzt.',
        quelle: 'REFERENZ.md (`sammlungen`) · LEITFADEN.md B3 (Felder)',
    },
    {
        id: 'bezugsfeld',
        begriff: 'Bezugsfeld',
        text: 'Woher ein Feld seinen Wert vorbelegt: eine Eigenschaft des Listeneintrags (eintrag.x), ein Feld derselben Vorlage oder bezug.team. Die Auswahl nennt genau die Pfade, die die Prüfung akzeptiert.',
        quelle: 'REFERENZ.md (`fuellstrategie`, `aus`) · LEITFADEN.md B7',
    },
    {
        id: 'baustein',
        begriff: 'Regel-Baustein',
        text: 'Der Rechentyp einer Regel (Mindestabstand, Höchstzahl je Zeitraum …). Welche Bausteine es gibt und welche Einstellungen sie haben, gibt die Baustein-Registry vor — die Auswahl zeigt genau diese Bausteine.',
        quelle: 'REFERENZ.md „Regel-Bausteine“ · LEITFADEN.md B8',
    },
    {
        id: 'anlasswert',
        begriff: 'Anlass (Wert)',
        text: 'Ein Anlass markiert einzelne Termine. In einer Bedingung wird er über seine Kennung angesprochen — die Auswahl bietet die Anlässe dieser Vorlage an.',
        quelle: 'LEITFADEN.md B6 (Anlässe)',
    },
    {
        id: 'variante',
        begriff: 'Variante',
        text: 'Eine von mehreren Ausführungen eines Gruppen-Feldes (Sonne/Regen). Eine Bedingung nennt die Variante über ihre Kennung — die Auswahl bietet die Varianten der Vorlage an.',
        quelle: 'REFERENZ.md (`variante`) · LEITFADEN.md B3',
    },
    {
        id: 'eingebaute_liste',
        begriff: 'Eingebaute Liste',
        text: 'Die Liedliste „lieder“ gehört zur App und wird nicht angelegt. Sie steht in jeder Liste-Auswahl zur Verfügung.',
        quelle: 'REFERENZ.md (`sammlungen`)',
    },
    {
        id: 'fremde_vorlage',
        begriff: 'Andere Planvorlage',
        text: 'Ein planübergreifender Verweis (Übung zählt in einer anderen Vorlage, gemeinsamer Abstand). Die Auswahl bietet die Planvorlagen an, für die du berechtigt bist — die eigene Vorlage nicht, denn sie wäre kein Verweis.',
        quelle: 'REFERENZ.md (`fremd_feld`) · LEITFADEN.md B8',
    },
]

/** Erklärung zu einer Kennung (oder `null`, wenn es keine gibt). */
export function erklaerung(id) {
    return ERKLAERUNGEN.find((e) => e.id === id) || null
}

/**
 * Die Erklärungen eines Abschnitts — in der Reihenfolge der Seite, ohne
 * Doppelte. Abschnitte ohne eigene Begriffe zeigen alle Erklärungen.
 */
export function erklaerungenFuer(abschnittId) {
    const a = ABSCHNITTE.find((s) => s.id === abschnittId)
    if (!a || !Array.isArray(a.erklaerung) || !a.erklaerung.length) return ERKLAERUNGEN.slice()
    const ids = [...new Set(a.erklaerung)]
    return ids.map((id) => erklaerung(id)).filter(Boolean)
}

/**
 * Platzhaltertext für einen Begriff, zu dem die Doku keine Erklärung hergibt.
 * Wird im Abschlussbericht als Lücke aufgeführt — nicht stillschweigend
 * erfunden.
 */
export const PLATZHALTER = 'Erklärung fehlt noch — dieser Begriff wird in der Doku noch beschrieben.'

// ── Aktiver Abschnitt beim Scrollen ────────────────────────────────────────

/** Abstand der Lesekante unterhalb des Fensterrands (px). */
export const LESEKANTE = 120

/**
 * Höchstabstand des letzten Abschnitts oberhalb der Lesekante am Seitenende
 * (px, zusätzlich zur Lesekante). Am Seitenende steht der letzte Abschnitt
 * oft nur wenig unter der Kante, weil darunter kein weiterer Inhalt folgt —
 * ohne diesen Puffer bliebe die Markierung auf dem vorletzten Eintrag stehen.
 */
export const ENDE_PUFFER = 200

/**
 * Welcher Abschnitt gilt, wenn die Überschriften bei diesen Positionen
 * stehen?
 *
 * @param {{id: string, top: number}[]} positionen  Oberkante je Abschnitt,
 *        gemessen ab der Oberkante des Ansichtsfensters (Wert wie aus
 *        `getBoundingClientRect().top`), in der Reihenfolge der Seite.
 * @param {number} [kante]  Lesekante; Vorgabe LESEKANTE.
 * @returns {string} Kennung des Abschnitts; vor dem ersten bleibt es der erste.
 */
/**
 * Steht man am Seitenende? Dann fehlt unter dem letzten Abschnitt der
 * Fensterinhalt, und er ist „erreicht“, obwohl er die Lesekante verfehlt.
 *
 * Prüfbar an den Positionen: der Abstand zwischen dem letzten und dem
 * vorletzten Abschnitt ist kleiner als die Lesekante. Bei echten Abschnitten
 * ist er größer (mehrere Hundert Pixel) — der Test mit knappen Abständen ist
 * dagegen ein Abschnittsende mit wenig Inhalt.
 */
function istSeitenende(liste, kante) {
    if (liste.length < 2) return true
    const letzter = liste[liste.length - 1].top
    const vorletzter = liste[liste.length - 2].top
    if (typeof letzter !== 'number' || typeof vorletzter !== 'number') return false
    if (!Number.isFinite(letzter) || !Number.isFinite(vorletzter)) return false
    return letzter - vorletzter < kante
}

export function aktiverAbschnitt(positionen, kante = LESEKANTE) {
    const liste = (Array.isArray(positionen) ? positionen : [])
        .filter((p) => p && typeof p.id === 'string')
    if (!liste.length) return ERSTER_ABSCHNITT
    const zahl = (p) => (typeof p.top === 'number' && Number.isFinite(p.top) ? p.top : null)
    // Unter der Lesekante gilt die Überschrift als passiert (`top - kante <= 0`).
    const unterDerKante = (p) => zahl(p) !== null && p.top - kante <= 0
    // Liegt sie dabei so weit oben, dass sie HINTER dem klebenden Band der
    // Sprungleiste verschwindet (`top < -BAND_PX`)? Genau das passiert beim
    // Sprung: `scrollIntoView` setzt die Überschrift auf die Oberkante. Sie
    // ist dann im Bild nicht zu sehen und darf nicht als „hier stehe ich“
    // gelten — sonst springt die Markierung nach dem Nachmessen weiter.
    const hinterDemBand = (p) => zahl(p) !== null && p.top < -BAND_PX
    // Gezählt werden die Abschnitte der Seite bis zur ersten, die noch unter
    // der Lesekante steht; davon fallen die hinter dem Band weg.
    let treffer = liste[0].id
    let erreichte = 0
    let sichtbar = 0
    let letzteErreichte = liste[0].id
    for (const p of liste) {
        if (!unterDerKante(p)) {
            if (zahl(p) !== null) break
            continue
        }
        erreichte++
        letzteErreichte = p.id
        if (hinterDemBand(p)) continue
        treffer = p.id
        sichtbar++
    }
    // Am Seitenende gilt der letzte Abschnitt: mindestens einer ist erreicht
    // (man steht nicht mehr oben) und der letzte steht höchstens eine
    // Lesekante tiefer als der erreichte. Ohne diese Regel bliebe die
    // Markierung auf dem vorletzten Eintrag stehen, obwohl der letzte
    // vollständig im Bild ist.
    const letzter = liste[liste.length - 1]
    if (erreichte && istSeitenende(liste, kante)) return letzter.id
    // Stehen alle erreichten hinter dem Band (sehr weit gescrollt), gilt der
    // zuletzt erreichte — beim Öffnen ist das der erste Abschnitt.
    if (!sichtbar) return letzteErreichte
    return treffer
}


/**
 * Zähler eines Abschnitts aus der Definition (Anzahl Einträge) oder `null`,
 * wenn der Abschnitt keine Zahl trägt.
 */
export function zaehler(abschnittId, definition) {
    const a = ABSCHNITTE.find((s) => s.id === abschnittId)
    if (!a || !a.zaehler) return null
    const wert = definition ? definition[a.zaehler] : null
    return Array.isArray(wert) ? wert.length : 0
}

/** Sprungziel im Markup (`#pr-pe-<id>`) — EINE Quelle für Liste und Köpfe. */
export function zielId(abschnittId) {
    return 'pr-pe-' + abschnittId
}

/**
 * Höhe des Materialbands, hinter dem eine Überschrift nicht mehr als
 * „erreicht“ gilt (px).
 *
 * Die Sprungleiste ist ab 900 px `sticky` unter der Oberkante des
 * Scroll-Behälters: eine Überschrift, die oben klebt, liegt HINTER dem Band
 * und ist unsichtbar. Mit der einfachen Regel („Oberkante über der
 * Lesekante“) meldete die Leiste beim Klick auf „Felder“ deshalb schon
 * „Anlässe“ — der Sprung landete richtig, die Markierung aber daneben. Ein
 * Abschnitt gilt erst, wenn seine Oberkante tiefer als dieses Band steht.
 */
export const BAND_PX = 44

/**
 * Wie weit eine Überschrift über der Lesekante stehen darf, um als erreicht
 * zu gelten — abhängig von der Breite, weil unter 900 px die Sprungleiste als
 * waagerechtes Band über der Seite liegt und darüber kein Platz mehr ist.
 */
export function lesekanteFuer(breite, kante = LESEKANTE) {
    return breite < SCHMAL_AB_PX ? kante + BAND_PX : kante
}

/** Unter dieser Breite liegt die Sprungleiste waagerecht über der Seite. */
export const SCHMAL_AB_PX = 900

/**
 * Lässt sich das Element messen? `display:none` (etwa der JSON-Reiter) und
 * `visibility:hidden` liefern Rechtecke mit Größe 0 — solche Werte dürfen
 * nicht als Position gelten, sonst springt die Markierung an den Anfang.
 */
export function istMessbar(rechteck) {
    return !!rechteck && rechteck.width > 0 && rechteck.height > 0
}

/**
 * Ist die Breite breit genug für die Erklärspalte? Unter 1200 px entfällt sie
 * (Entwurf C3: beide Seitenspalten brauchen ~490 px). Die Regel steht
 * zusätzlich als CSS-Medienabfrage in der Seite; dieser Wert dient dem
 * deutlich sichtbaren Zustand (aria-hidden) und den Tests.
 */
export const ERKLAERSPALTE_AB_PX = 1200

export function erklaerspalteZeigen(breite) {
    return Number(breite) >= ERKLAERSPALTE_AB_PX
}
