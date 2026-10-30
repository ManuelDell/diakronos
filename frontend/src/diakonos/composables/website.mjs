/**
 * WEB-3 — Prüfbare Regeln der Website-Oberfläche (ohne Vue).
 *
 * Warum eine eigene Datei: Sichtbarkeit, Zustandstext und Fehlerdeutung sind
 * FACHLOGIK, die ein Test ausführen kann. In der Komponente wären sie nur als
 * Quelltext lesbar (`assert.match`), also nicht nachweisbar. Hier stehen sie
 * als reine Funktionen — dieselbe Aufteilung wie bei `anzeigename.mjs` oder
 * `eingabeart.mjs`.
 *
 * Vertrag des Servers (WEB-1b, Abschlusskommentar der Elternkarte):
 *
 *   GET  website.status          -> {status, version, site_count, url, warnung}
 *        status: "nicht_konfiguriert" | "nicht_erreichbar" | "verbunden"
 *   POST website.login_uebergabe -> {url}   (X-Frappe-CSRF-Token, NUR POST)
 *
 * Fehlerbilder kommen NICHT über `exc_type` (SEC-8-Allowlist: nur
 * CSRFTokenError/SessionExpired/PermissionError), sondern über den
 * HTTP-Status: 401 Sitzung · 403 keine Berechtigung · 409 Verknüpfung nötig
 * (Meldung des Servers übernehmen) · 503 nicht angeschlossen/erreichbar.
 */

/**
 * Rollen, die Website-Funktionen nutzen dürfen — Deckungsgleich mit
 * `WEBSITE_ROLLEN` im Backend (`website/primo.py`). Reihenfolge und
 * Schreibweise sind der Vertrag; ein Test vergleicht beide Listen.
 */
export const WEBSITE_ROLLEN = ['System Manager', 'Administrator', 'Website-Moderator']

/**
 * Darf dieser Benutzer den Bereich „Website“ sehen?
 *
 * Grundlage ist die Rollenliste der Sitzung (`window.__DIakonosBOOT.roles`,
 * dieselbe Quelle wie die übrigen rollengeschützten Einträge). Nur Komfort:
 * der Server prüft jede Anfrage erneut (fail closed, 403).
 *
 * @param {{rollen?: string[]|null}} [optionen]
 * @returns {boolean}
 */
export function darfWebsite({ rollen = null } = {}) {
    const vorhanden = new Set(
        (Array.isArray(rollen) ? rollen : []).map(r => String(r || '').trim()),
    )
    return WEBSITE_ROLLEN.some(r => vorhanden.has(r))
}

/**
 * Zustand der Anbindung als anzeigbarer Satz.
 *
 * Die drei Serverzustände bekommen je einen eigenen Ton (für `DkBadge`) und
 * einen Knopftext — „Verbindung prüfen“ ist überall derselbe, weil er nur den
 * Status neu abfragt.
 *
 * Unbekannte Zustände (älterer/neuerer Server) werden NICHT als „verbunden“
 * ausgegeben: eine erfundene Erfolgsmeldung wäre schlimmer als ein ehrliches
 * „unbekannt“.
 *
 * @param {string} status  Serverwert
 * @returns {{zustand: string, titel: string, ton: string, text: string}}
 */
export function zustandsText(status) {
    switch (String(status || '')) {
        case 'verbunden':
            return {
                zustand: 'verbunden',
                titel: 'Verbunden',
                ton: 'ok',
                text: 'Diakronos erreicht die Website. Redakteure können von hier aus in Primo arbeiten.',
            }
        case 'nicht_erreichbar':
            return {
                zustand: 'nicht_erreichbar',
                titel: 'Nicht erreichbar',
                ton: 'err',
                text: 'Die Website-Adresse ist eingetragen, aber Primo antwortet nicht. '
                    + 'Läuft der Primo-Stack, und stimmt die Adresse?',
            }
        case 'nicht_konfiguriert':
            return {
                zustand: 'nicht_konfiguriert',
                titel: 'Nicht angeschlossen',
                ton: 'neutral',
                text: 'Die Website ist noch nicht angeschlossen. Die Anbindung ist optional — '
                    + 'Diakronos arbeitet ohne sie vollständig. Die Einrichtung steht unten.',
            }
        default:
            return {
                zustand: 'unbekannt',
                titel: 'Zustand unbekannt',
                ton: 'warn',
                text: 'Der Server hat einen unbekannten Zustand gemeldet. '
                    + 'Bitte die Verbindung erneut prüfen.',
            }
    }
}

/**
 * Verbindungszeile: Version und Seitenzahl — nur, was der Server geliefert hat.
 * Fehlende Werte werden ausgelassen, nie als 0 erfunden.
 *
 * @param {{status?: string, version?: string|null, site_count?: number|null}} daten
 * @returns {string}  z. B. „Primo v3.3.1 · 3 Seiten“ oder ''
 */
export function verbindungsDetails(daten) {
    const quelle = daten || {}
    if (String(quelle.status || '') !== 'verbunden') return ''
    const teile = []
    if (quelle.version) teile.push(`Primo ${String(quelle.version).trim()}`)
    const anzahl = Number(quelle.site_count)
    if (Number.isFinite(anzahl) && anzahl >= 0) {
        teile.push(anzahl === 1 ? '1 Seite' : `${anzahl} Seiten`)
    }
    return teile.join(' · ')
}

/**
 * Fehler beim Öffnen der Übergabe in Klartext (S2).
 *
 * Unterschieden wird am HTTP-STATUS, nicht am Ausnahmennamen (SEC-8). 409 trägt
 * eine fachliche Meldung des Servers („Verknüpfung durch Admin nötig“) — die
 * wird unverändert gezeigt, damit die Verwaltung weiß, was zu tun ist.
 *
 * @param {{status?: number, message?: string}|null} fehler
 * @returns {string}
 */
export function uebergabeFehlertext(fehler) {
    const status = Number(fehler?.status)
    const meldung = String(fehler?.message || '').trim()
    switch (status) {
        case 401:
            return 'Deine Sitzung ist abgelaufen. Bitte neu anmelden und erneut versuchen.'
        case 403:
            return 'Du darfst die Website nicht öffnen. Dafür braucht es die Rolle '
                + 'System Manager, Administrator oder Website-Moderator.'
        case 409:
            return meldung || 'Für dieses Konto besteht in Primo bereits ein Zugang. '
                + 'Die Verknüpfung muss durch einen Admin eingerichtet werden.'
        case 417:
            return 'Die Sicherheitsprüfung des Browsers ist fehlgeschlagen. '
                + 'Bitte die Seite neu laden und erneut versuchen.'
        case 503:
            return 'Die Website ist gerade nicht erreichbar oder nicht angeschlossen. '
                + 'Bitte später erneut versuchen.'
        default:
            return meldung || 'Die Website ließ sich nicht öffnen. Bitte später erneut versuchen.'
    }
}

/**
 * Prüft, ob der Server eine brauchbare Übergabe-Adresse geliefert hat.
 *
 * Zugelassen sind ausschließlich `http(s)`-Adressen. Ein `javascript:`- oder
 * `data:`-Ziel aus einer manipulierten Antwort würde beim `window.open` Code
 * ausführen — deshalb die Prüfung hier, vor dem Öffnen.
 *
 * @param {unknown} url
 * @returns {string}  die Adresse oder '' wenn unbrauchbar
 */
export function sichereUebergabeUrl(url) {
    const text = String(url || '').trim()
    if (!text) return ''
    if (!/^https?:\/\//i.test(text)) return ''
    return text
}

/**
 * Hinweistext zur Sitzungsdauer (D, WEB-1b): Das Primo-Token ist nicht
 * verlängerbar, die Sitzung endet mit ihm.
 *
 * @param {number} sekunden  Token-Dauer in Sekunden (Server: 14400 = 4 h)
 * @returns {string}
 */
export function sitzungsHinweis(sekunden) {
    const wert = Number(sekunden)
    if (!Number.isFinite(wert) || wert <= 0) {
        return 'Die Sitzung in Primo läuft nach einiger Zeit ab. Danach erneut über Diakronos öffnen.'
    }
    const stunden = wert / 3600
    const dauer = Number.isInteger(stunden)
        ? `${stunden} Stunden`
        : `${Math.max(1, Math.round(wert / 60))} Minuten`
    return `Die Sitzung in Primo endet nach ${dauer} (das Token lässt sich nicht verlängern). `
        + 'Danach erneut über Diakronos öffnen.'
}

/**
 * Kurzanleitung „Primo anschließen“ als Text (S1).
 *
 * Inhalt aus `deploy/primo/ANLEITUNG.md` (WEB-2) und `docs/BETRIEBSANLEITUNG.md`.
 * Bewusst als DATEN und nicht als Fließtext im Template: die Einstellungsseite
 * zeigt eine nummerierte Liste, und der Test kann die Schritte einzeln prüfen.
 * Die Werte sind die echten Einstellungsnamen (`PRIMO_URL`, …) — wer sie
 * abschreibt, findet sie in der `.env.example` wieder.
 */
export const ANSCHLUSS_SCHRITTE = [
    {
        titel: 'Primo-Stack starten',
        text: 'Im Repository liegt der fertige Primo-Stack unter deploy/primo. '
            + 'Dort .env anlegen und den Stack hochfahren: '
            + 'cp .env.example .env, dann docker compose -p diakronos-primo --env-file .env up -d. '
            + 'Prüfen mit curl http://127.0.0.1:8095/api/primo/info.',
    },
    {
        titel: 'Integrationskonto in Primo',
        text: 'In Primo ein Konto mit der Server-Rolle „developer“ anlegen — nur damit darf '
            + 'Diakronos Konten und Seiten pflegen. Dessen Zugang wird als Superuser hinterlegt.',
    },
    {
        titel: 'Werte in Diakronos eintragen (settings/.env)',
        text: 'PRIMO_URL = interne Adresse, wie der Server Primo erreicht '
            + '(z. B. http://192.168.1.11:8095). '
            + 'PRIMO_PUBLIC_URL = Adresse, die der Browser öffnet (z. B. https://website.example.org; '
            + 'leer = PRIMO_URL). '
            + 'PRIMO_SUPERUSER_EMAIL und PRIMO_SUPERUSER_PASSWORD (oder PRIMO_SUPERUSER_PASSWORD_FILE) '
            + '= Zugang des Integrationskontos.',
    },
    {
        titel: 'Diakronos neu starten und prüfen',
        text: 'Der Server liest die Einstellungen beim Start. Danach hier auf '
            + '„Verbindung prüfen“ — steht oben „Verbunden“, ist alles bereit.',
    },
]

/**
 * Wo die ausführliche Anleitung steht. Als TEXT in der Oberfläche, nicht als
 * Link ins Repository: der Betrieb liest die Dateien auf dem Server, nicht im
 * Browser (`docs/` liegt nicht im Image).
 */
export const ANLEITUNG_ORT = 'Die vollständige Anleitung steht im Repository in '
    + 'deploy/primo/ANLEITUNG.md und in docs/BETRIEBSANLEITUNG.md (Abschnitt Primo).'

/**
 * Die Interna, die Diakronos von Primo braucht — als Prüfliste für die
 * Einstellungsseite (nur Anzeige; gesetzt werden sie in settings/.env).
 */
export const BENOETIGTE_WERTE = [
    'PRIMO_URL',
    'PRIMO_PUBLIC_URL',
    'PRIMO_SUPERUSER_EMAIL',
    'PRIMO_SUPERUSER_PASSWORD',
]
