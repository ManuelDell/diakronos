/**
 * R6 — Beiträge/Wiki: Gruppe wählen, Gast-Links, Gastseite.
 *
 * EINE Stelle für die Regeln, die die Oberfläche braucht — ohne Vue, damit sie
 * mit `node --test` prüfbar ist. Die Rechte selbst entscheidet NIE diese Datei:
 * sie liest nur, was der Server antwortet (`anlegen`, `darf_bearbeiten`) und
 * baut daraus die Auswahlliste.
 *
 * Begriffe (Manuel 11.11.): HV = Hauptverantwortliche/r, MV =
 * Mitverantwortliche/r, GL = Gruppenleitung (Untergruppe). „Für alle Mitglieder
 * der Gemeinde“ statt „öffentlich“.
 *
 * UI-R6b: Die Liste der Anlegeorte kommt FERTIG vom Server
 * (`api.rechte.get_anlegeorte` → `{orte: [{gruppe, untergruppe, titel, tiefe,
 * gemeinde}]}`, Anzeigereihenfolge). Es gibt hier deshalb keine eigene
 * Gruppen-Hierarchie, keine Einzelfragen je Gruppe und keinen eigenen
 * Gemeinde-Text mehr — Titel und Reihenfolge sind die des Servers, und der
 * entscheidet auch die Rechte (dieselbe Regel wie beim Anlegen).
 *
 * UI-R6c: `GEMEINDE_TEXT` ist entfallen. Der Titel des gemeindeweiten Ortes
 * kommt wie jeder andere aus der Serverantwort (`STUFEN_TITEL` →
 * „Alle Mitglieder der Gemeinde“); fehlt er, ist die Antwort unvollständig und
 * der Ort wird verworfen, statt einen eigenen Text zu erfinden.
 */
import { serverZeit } from '../../shared/zeit.mjs'

/** Gültigkeit eines Gast-Links: Standard 3 Tage, 1–30 wählbar (Server). */
export const GAST_TAGE_STANDARD = 3
export const GAST_TAGE_MIN = 1
export const GAST_TAGE_MAX = 30
/** Kürzestes Passwort (Server: `gastlinks.MIN_PASSWORT`). */
export const GAST_PASSWORT_MIN = 8

/** Fehlertexte der öffentlichen Gastseite — wortgleich mit dem Server. */
export const GAST_FEHLER_ABGELAUFEN = 'Dieser Link ist ungültig oder abgelaufen.'
export const GAST_FEHLER_PASSWORT = 'Das Passwort stimmt nicht.'
export const GAST_FEHLER_ZUVIELE = 'Zu viele Versuche. Bitte versuche es später erneut.'

// ── Auswahl der Gruppe beim Anlegen ─────────────────────────────────────────

/**
 * Antwort von `rechte.get_anlegeorte(typ)` in die Form der Auswahl bringen.
 *
 * Der Server liefert bereits NUR die Einheiten, in denen diese Person anlegen
 * darf — in Anzeigereihenfolge (Gemeinde nur für den Administrator, dann je
 * Gruppe die Gruppe und ihre Untergruppen) und mit fertigem `titel` und
 * `tiefe`. Diese Funktion ordnet deshalb nichts um und filtert nichts: sie
 * übernimmt die Liste, wie sie kommt.
 *
 * `antwort` ist `{orte: [...]}` (oder die Liste selbst). Die Felder
 * `gruppe`/`untergruppe` sind genau die Werte, die
 * `create_beitrag`/`create_wiki_artikel` erwarten.
 *
 * UI-R6c: Ein Ort OHNE `titel` ist eine unvollständige Serverantwort und wird
 * verworfen — die Oberfläche erfindet keinen Ersatztext (früher stand hier
 * `GEMEINDE_TEXT` bzw. die rohe Kennung, und genau die landete im Editor).
 */
export function anlegeorteAusAntwort(antwort) {
    const orte = Array.isArray(antwort) ? antwort : (antwort?.orte || [])
    const zeilen = []
    for (const ort of orte) {
        if (!ort || typeof ort !== 'object') continue
        const gruppe = ort.gruppe || null
        const untergruppe = gruppe ? (ort.untergruppe || null) : null
        if (!gruppe && !ort.gemeinde) continue
        if (!ort.titel) continue
        zeilen.push({
            gruppe,
            untergruppe,
            titel: String(ort.titel),
            tiefe: Number.isInteger(ort.tiefe) ? ort.tiefe : (untergruppe ? 1 : 0),
            gemeinde: !gruppe,
        })
    }
    return zeilen
}

/** Optionswert der Auswahl: ein String, damit DkSelect/String-Vergleiche tragen. */
export function einheitWert(eintrag) {
    if (!eintrag) return ''
    if (!eintrag.gruppe) return 'gemeinde'
    return eintrag.untergruppe ? `${eintrag.gruppe}|${eintrag.untergruppe}` : eintrag.gruppe
}

/**
 * Umkehrung von `einheitWert` — liefert den ORT des Servers zum Optionswert.
 *
 * UI-R6c: Zurück kommt das ganze Ortsobjekt (samt `titel`), nicht mehr nur
 * `{gruppe, untergruppe}`. „Weiter“ im Auswahl-Dialog reichte früher nur die
 * beiden Kennungen weiter; der Editor konnte den Server-Titel damit nur über
 * eine zweite Suche in `optionen` wiederfinden. Jetzt reist er mit.
 *
 * @param {string} wert  Optionswert (`einheitWert`)
 * @param {Array} optionen  Orte vom Server
 * @returns {{gruppe: string|null, untergruppe: string|null, titel?: string}}
 *   der Ort; ohne Treffer die beiden Kennungen allein (dann gibt es keinen
 *   Titel zu zeigen — erfunden wird keiner).
 */
export function ortAusWert(wert, optionen = []) {
    const roh = String(wert ?? '')
    const treffer = (optionen || []).find(o => einheitWert(o) === roh)
    if (treffer) return { ...treffer }
    if (!roh || roh === 'gemeinde') return { gruppe: null, untergruppe: null }
    const [gruppe, untergruppe] = roh.split('|')
    return { gruppe: gruppe || null, untergruppe: untergruppe || null }
}

/**
 * Vorauswahl beim Öffnen des Editors.
 *
 * `fest` (z. B. die Gruppe der Gruppenseite) hat Vorrang, wenn sie in der Liste
 * steht. Sonst: genau EINE Möglichkeit → diese; mehrere → leer (die Person
 * muss wählen); keine → leer.
 */
export function vorauswahl(optionen, fest = null) {
    const liste = optionen || []
    if (fest) {
        const wert = einheitWert(fest)
        if (liste.some(o => einheitWert(o) === wert)) return wert
    }
    if (liste.length === 1) return einheitWert(liste[0])
    return ''
}

/**
 * Anzeigetext einer Einheit (für Hinweise und Fehlermeldungen).
 *
 * UI-R6c: Es gilt ALLEIN der `titel` des Servers. Vorher stand hier ein
 * eigener Gemeinde-Text und eine zusammengesetzte Kennung („GR-Chor ·
 * UG-Blas“) als Rückfall — beides ist weg: fehlt der Titel, ist die Antwort
 * des Servers unvollständig, und dann wird hier nichts erfunden.
 */
export function einheitText(eintrag) {
    if (!eintrag) return ''
    return eintrag.titel || ''
}

/**
 * Was steht im Auswahlfeld wirklich?
 *
 * Befund R6 (Messung im echten Browser): `<select :value="">` mit Options,
 * von denen KEINE leer ist, hat `selectedIndex === -1` — das Feld zeigt
 * nichts, und ein „Weiter“, das nur den Wert liest, bliebe gesperrt. Wer
 * also nichts Eigenes gewählt hat, bekommt hier die Vorauswahl bzw. den
 * ersten Eintrag — und die Vorlage BINDET diesen Wert zurück
 * (`:model-value="gewaehlt"`), damit Feld und Knopf dasselbe sagen.
 *
 * Die alte Annahme („der Browser zeigt ohne `selected` den ersten Eintrag,
 * Wert bleibt leer“) trifft nicht zu: ohne passende Option ist die Auswahl
 * leer. Diese Funktion bleibt trotzdem die eine Regel dafür.
 */
export function gewaehlteEinheit(optionen, { eigeneWahl = '', start = '' } = {}) {
    const werte = (optionen || []).map(einheitWert)
    if (eigeneWahl && werte.includes(eigeneWahl)) return eigeneWahl
    if (start && werte.includes(start)) return start
    return werte[0] || ''
}

// ── Gast-Links ──────────────────────────────────────────────────────────────

/**
 * Prüfung des Freigabe-Dialogs VOR dem Serveraufruf.
 * Liefert `null` (alles in Ordnung) oder `{feld, meldung}`.
 */
export function gastlinkPruefung({ passwort = '', wiederholung = '', tage = GAST_TAGE_STANDARD } = {}) {
    const p = String(passwort ?? '')
    if (p.length < GAST_PASSWORT_MIN) {
        return { feld: 'passwort', meldung: `Das Passwort braucht mindestens ${GAST_PASSWORT_MIN} Zeichen.` }
    }
    if (p !== String(wiederholung ?? '')) {
        return { feld: 'wiederholung', meldung: 'Die beiden Passwörter sind nicht gleich.' }
    }
    const zahl = Number(tage)
    if (!Number.isInteger(zahl) || zahl < GAST_TAGE_MIN || zahl > GAST_TAGE_MAX) {
        return { feld: 'tage', meldung: `Die Gültigkeit liegt zwischen ${GAST_TAGE_MIN} und ${GAST_TAGE_MAX} Tagen.` }
    }
    return null
}

/**
 * Vollständige Adresse des Gast-Links aus dem Token.
 *
 * Die Seite ist der öffentliche Einstieg `…/gastinhalt`; der Token steht im
 * Hash (`#/gast/<token>`), den der Server nie sieht. `basis` ist die Adresse
 * der Seite OHNE Hash (`location.href.split('#')[0]`) — so bleibt ein
 * Betriebs-Präfix (DIAKRONOS_BASE_PATH) erhalten. Der Token wird kodiert; er
 * enthält nie ein `#`.
 */
export function gastLinkAdresse(basis, token) {
    const rein = String(basis ?? '').split('#')[0]
    return `${rein}#/gast/${encodeURIComponent(String(token ?? ''))}`
}

/** Fester öffentlicher Einstieg der Gastseite (Server: `OEFFENTLICHE_EINTRAEGE`). */
export const GAST_EINSTIEG = 'gastinhalt'

/**
 * Adresse des Gast-Links für die ANZEIGE — unabhängig davon, wo die
 * freigebende Person gerade steht (Beiträge, Wiki, Gruppenseite).
 *
 * **Die Adresse ist eine Funktion des ANSEHENDEN Dokuments, deshalb reicht sie
 * der Aufrufer herein**: `{ursprung, pfad}` = `location.origin` und der
 * Betriebs-Präfix aus `basisPfad()` (`shared/basis.js`), gesetzt in der App.
 * So bleibt Diakronos unter `DIAKRONOS_BASE_PATH` richtig und die Datei hier
 * importfrei (prüfbar mit `node --test`).
 */
export function gastLinkAdresseFuer({ ursprung = '', pfad = '' } = {}, token) {
    const herkunft = String(ursprung).replace(/\/+$/, '')
    const basis = String(pfad ?? '').replace(/\/+$/, '')
    return gastLinkAdresse(`${herkunft}${basis}/${GAST_EINSTIEG}`, token)
}

/**
 * Zeile der Gast-Link-Liste: Status in Worten (kein Serverfehlertext).
 *
 * Der Server liefert `aktiv` bereits fertig (`gastlinks.liste`: nicht
 * widerrufen UND Ablauf in der Zukunft). Dieses Feld entscheidet deshalb —
 * die Uhr des Geräts geht falsch, die des Servers nicht. Nur wenn `aktiv`
 * fehlt (ältere Antwort), wird aus `ablauf` und der Geräteuhr geschlossen.
 */
export function gastlinkStatus(link, jetzt = Date.now()) {
    if (!link) return ''
    if (link.widerrufen) return 'Widerrufen'
    if (typeof link.aktiv === 'boolean') return link.aktiv ? 'Aktiv' : 'Abgelaufen'
    const ablauf = zeitpunkt(link.ablauf)
    if (ablauf === null) return 'Abgelaufen'
    return ablauf > jetzt ? 'Aktiv' : 'Abgelaufen'
}

/** Ist der Link noch benutzbar? (Server sagt es; hier nur die Anzeige-Logik.) */
export function gastlinkAktiv(link, jetzt = Date.now()) {
    return gastlinkStatus(link, jetzt) === 'Aktiv'
}

/**
 * Server-Zeitstempel der Gast-Links → Millisekunden.
 *
 * Die Zeitstempel sind UTC ohne Zone; wie sie zu lesen sind, steht EINMAL in
 * `shared/zeit.mjs` (`serverZeit`). Hier bleibt nur die Rückgabe als Zahl —
 * dadurch gibt es keine zweite Auslegung derselben Serverzeit im Frontend.
 */
export function zeitpunkt(wert) {
    const d = serverZeit(wert)
    return d ? d.getTime() : null
}

/**
 * Fehlerantwort der öffentlichen Gastseite → einer der drei festen Texte.
 *
 * Quelle ist der HTTP-Status (der Server antwortet 404 = ungültig/abgelaufen,
 * 403 = falsches Passwort ODER zu viele Versuche). Bei 403 entscheidet der
 * Servertext, welcher der beiden Fälle gilt — steht dort „Versuche“, ist es die
 * Bremse. Alles andere bleibt beim Passwort-Hinweis, damit eine unerwartete
 * Antwort keine „ungültig“-Meldung erfindet.
 */
export function gastFehlertext(status, servertext = '') {
    const text = String(servertext || '').trim()
    if (status === 404) return GAST_FEHLER_ABGELAUFEN
    if (status === 403) {
        if (/versuch/i.test(text)) return GAST_FEHLER_ZUVIELE
        return GAST_FEHLER_PASSWORT
    }
    if (status === 429) return GAST_FEHLER_ZUVIELE
    return text || 'Der Inhalt konnte nicht geladen werden. Bitte versuche es erneut.'
}

/**
 * Nutzlast der Antwort von `gast_inhalt` auspacken.
 *
 * Die Compat-Schicht des Servers legt JEDE Nutzlast unter `message`
 * (`{"message": {"typ", "titel", "inhalt", "datum"}}`). Die Gastseite spricht
 * den Endpunkt direkt per `fetch` an (ohne `apiCall`, das auspackt) — ohne
 * diesen Schritt blieben Titel, Datum und Inhalt leer, obwohl der Server sie
 * liefert. Fehlerantworten tragen `message` als TEXT; die bleiben unberührt.
 */
export function gastNutzlast(daten) {
    const roh = daten?.message
    if (roh && typeof roh === 'object' && !Array.isArray(roh)) return roh
    return daten && typeof daten === 'object' ? daten : {}
}
