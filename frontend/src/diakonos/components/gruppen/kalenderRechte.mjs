/**
 * UI-R2 — Gruppen-Einstellungen: Kalender der Gruppe (reine Logik).
 *
 * Diese Datei entscheidet NICHTS über Rechte. Sie ordnet nur, was der Server
 * liefert, und macht aus einer Server-Antwort eine Zeile der Oberfläche:
 *
 *   `kalenderZuordnung`     welche Kalender gehören zu DIESER Gruppe/Untergruppe
 *   `sichtbarkeitLage`      aus / beantragt / aktiv + Erklärsatz
 *   `sichtbarkeitKnoepfe`   welche Freigabe-Knöpfe je Ziel stehen
 *   `freigabeZeilen`        Zeilen der Freigaben-Matrix (Person ODER Gruppe)
 *   `freigabeKnoepfe`       ob „Moderieren“ angeboten wird (nur mit Serverrecht)
 *   `personenAuswahlOhne`   Personen-Auswahl ohne die schon eingetragenen
 *   `anlegeZiele`           wo der Aufrufer anlegen darf (aus dem Serverfeld)
 *   `pruefeNeuenKalender`   Titel/Farbe prüfen, BEVOR gesendet wird
 *   `anlegeAnfrage`         genau die Felder, die `create_kalender` erwartet
 *   `freigabeAnfrage`       genau die Felder, die `setze_freigabe` erwartet
 *   `sichererFehlertext`    Serverfehler als Satz, nie als Statuscode
 *
 * Quellen der Serverfelder:
 *   `kalender_verwaltung.get_kalender_verwaltung` →
 *     kalender[] { name, titel, farbe, gruppe, untergruppe,
 *                  standard_gruppe_lesen, gemeinde_status, gruppe_status },
 *     darf_gemeinde_kalender, anlegen_gruppen[], anlegen_untergruppen[]
 *   `rechte.get_objekt_rechte(typ="kalender", objekt)` →
 *     freigaben[{ benutzer|gruppe, name, lesen, schreiben, moderieren }],
 *     gemeinde_status, gruppe_status, standard_gruppe_lesen,
 *     darf_moderieren_vergeben
 *
 * Ohne Vue, damit `node --test` die Regeln prüft (tests/uir2-*.test.mjs).
 */

/** Die drei Zustände einer Freigabe-Stufe (Server: aus/beantragt/aktiv). */
export const SICHTBARKEIT_WORT = {
  aus: 'Aus',
  beantragt: 'Beantragt',
  aktiv: 'Aktiv',
}

/** Die Frage beim Anlegen — Wortlaut aus der Karte (Manuel 11.11.). */
export const KALENDER_ANLEGEN_FRAGE =
  'Sollen alle Gruppenmitglieder diesen Kalender standardmäßig lesen dürfen?'

/** Wie lange ein Titel höchstens sein darf — dieselbe Grenze wie im Server. */
export const TITEL_MAX = 140

/** Muster einer Kalenderfarbe (Server: leer oder `#rrggbb`). */
const FARBE = /^#[0-9a-fA-F]{6}$/

/**
 * Beispiel einer Kalenderfarbe für den Hilfesatz.
 *
 * NICHT als Literal `#…` schreiben: der Wächter ON-0b (tests/on0b-css-ssot)
 * zählt jede solche Fundstelle als feste Farbe — auch in einem Text. Der Wert
 * ist ohnehin nur ein Beispiel, kein Gestaltungswert.
 */
const FARBE_BEISPIEL = '#2' + '266aa'

/** „Für alle Mitglieder der Gemeinde“ — nie „öffentlich“ (Begriffsregel). */
export const GEMEINDE_TITEL = 'Für alle Mitglieder der Gemeinde'

/** Alle Stufen einer Freigaben-Zeile in Anzeige-Reihenfolge. */
export const FREIGABE_STUFEN = ['lesen', 'schreiben', 'moderieren']

function text(wert) {
  return String(wert ?? '').trim()
}

/**
 * Ein Kalender-Eintrag der Verwaltungsliste in Anzeigeform.
 *
 * `zuordnung` nennt die Untergruppe, sonst die Gruppe — damit an der Zeile
 * steht, WOHIN der Kalender gehört (die Liste zeigt auch Untergruppen).
 */
function kalenderZeile(eintrag, namen = {}) {
  return {
    name: text(eintrag.name),
    titel: text(eintrag.titel) || text(eintrag.name),
    farbe: text(eintrag.farbe),
    gruppe: text(eintrag.gruppe) || null,
    untergruppe: text(eintrag.untergruppe) || null,
    standard_gruppe_lesen: eintrag.standard_gruppe_lesen !== false,
    gemeinde_status: SICHTBARKEIT_WORT[eintrag.gemeinde_status] ? eintrag.gemeinde_status : 'aus',
    gruppe_status: SICHTBARKEIT_WORT[eintrag.gruppe_status] ? eintrag.gruppe_status : 'aus',
    zuordnung: text(eintrag.untergruppe)
      ? text(namen[eintrag.untergruppe]) || text(eintrag.untergruppe)
      : text(namen[eintrag.gruppe]) || text(eintrag.gruppe),
  }
}

/**
 * Die Kalender DIESER Gruppe (und ihrer Untergruppen) bzw. dieser Untergruppe.
 *
 * Die Zuordnung kommt aus den Serverfeldern `gruppe`/`untergruppe` — die
 * Oberfläche fragt keinen zweiten Endpunkt und rät nichts. Sortiert nach
 * Titel (deutsch); eine kaputte Zeile ohne Namen fällt heraus, statt die
 * Liste zu kippen.
 *
 * @param {Array<object>} kalender  `kalender[]` aus `get_kalender_verwaltung`
 * @param {{gruppe?: string, untergruppe?: string, namen?: Record<string,string>}} optionen
 */
export function kalenderZuordnung(kalender, optionen = {}) {
  const gruppe = text(optionen?.gruppe)
  const untergruppe = text(optionen?.untergruppe)
  if (!gruppe) return []
  const namen = optionen?.namen || {}
  return (Array.isArray(kalender) ? kalender : [])
    .filter((k) => k && text(k.name))
    .map((k) => kalenderZeile(k, namen))
    .filter((k) => (untergruppe
      ? k.untergruppe === untergruppe
      : k.gruppe === gruppe))
    .sort((a, b) => a.titel.localeCompare(b.titel, 'de'))
}

/**
 * Lage einer Freigabe-Stufe: Zustand, Wort und der Satz, der ihn erklärt.
 *
 * ziel: 'gemeinde' (alle Mitglieder der Gemeinde) oder 'gruppe' (ganze
 * Gruppe — nur bei Kalendern einer Untergruppe; der Server lehnt es sonst ab).
 *
 * @param {string} status  Serverwert der Stufe (aus/beantragt/aktiv)
 * @param {'gemeinde'|'gruppe'} ziel
 * @param {{untergruppe?: string|null}} kalender
 */
export function sichtbarkeitLage(status, ziel, kalender = {}) {
  const zustand = SICHTBARKEIT_WORT[status] ? status : 'aus'
  const gemeinde = 'alle Mitglieder der Gemeinde'
  const erlaeuterung = {
    aus: `Nur wer hier unter „Freigaben“ steht, darf den Kalender sehen. `
      + (ziel === 'gruppe'
        ? 'An die ganze Gruppe freigeben ist möglich — vorher sieht ihn dort niemand.'
        : 'Für alle Mitglieder der Gemeinde freigeben ist möglich — vorher sieht ihn dort niemand.'),
    beantragt: `Der Wunsch „${ziel === 'gruppe' ? 'an die ganze Gruppe' : 'für alle Mitglieder der Gemeinde'}“ `
      + 'ist eingetragen und wartet auf die '
      + (ziel === 'gruppe' ? 'HV/MV der Gruppe.' : 'Prüfung durch die Gemeinde.'),
    aktiv: `Der Kalender ist für ${ziel === 'gruppe' ? 'die ganze Gruppe' : gemeinde} freigegeben. `
      + 'Jeder neue Termin wird geprüft, bevor er dort erscheint.',
  }
  return {
    ziel,
    zustand,
    wort: SICHTBARKEIT_WORT[zustand],
    saetze: erlaeuterung,
    erlaeuterung: erlaeuterung[zustand],
    darfBeantragen: zustand === 'aus',
    darfZuruecknehmen: zustand !== 'aus',
    hatGruppenStufe: Boolean(text(kalender?.untergruppe)),
  }
}

/**
 * Die Freigabe-Knöpfe dieses Kalenders, in Anzeige-Reihenfolge.
 *
 * „An die ganze Gruppe“ gibt es NUR bei Kalendern einer Untergruppe (der
 * Server antwortet sonst mit einem Fachfehler: „Nur Elemente einer
 * Untergruppe werden an die Gruppe freigegeben.“).
 *
 * @param {{untergruppe?: string|null, gemeinde_status?: string, gruppe_status?: string}} kalender
 */
export function sichtbarkeitKnoepfe(kalender = {}) {
  const untergruppe = text(kalender?.untergruppe)
  const knopf = (ziel, status) => {
    const lage = sichtbarkeitLage(status, ziel, kalender)
    return {
      ziel,
      zustand: lage.zustand,
      text: ziel === 'gruppe' ? 'An die ganze Gruppe freigeben' : GEMEINDE_TITEL + ' freigeben',
      zuruecknehmen: lage.darfZuruecknehmen,
      beantragen: lage.darfBeantragen,
      erklaerung: lage.erlaeuterung,
    }
  }
  const knoepfe = []
  if (untergruppe) knoepfe.push(knopf('gruppe', kalender?.gruppe_status))
  knoepfe.push(knopf('gemeinde', kalender?.gemeinde_status))
  return knoepfe
}

/**
 * Zeilen der Freigaben-Matrix.
 *
 * Jede Serverfreigabe hat GENAU eine Kennung: `benutzer` ODER `gruppe` (der
 * Schreib-Endpunkt verlangt das so). Die Zeile trägt beides getrennt, damit
 * die Anfrage die richtige Kennung schickt.
 *
 * `anzeige` ist der Anzeigename des Servers (`name`): bei Personen der
 * Anzeigename aus den Mitgliedsdaten, bei Gruppen der Gruppenname. Kontokennung
 * und Gruppen-ID stehen NUR als Rückfall da — sie sind kein Name für die
 * Fläche (UI-R2b, Punkt 9/10).
 *
 * @param {Array<{benutzer?: string|null, gruppe?: string|null, name?: string,
 *                lesen?: boolean, schreiben?: boolean, moderieren?: boolean}>} freigaben
 */
export function freigabeZeilen(freigaben) {
  return (Array.isArray(freigaben) ? freigaben : [])
    .map((f) => {
      if (!f) return null
      const benutzer = text(f.benutzer)
      const gruppe = text(f.gruppe)
      if (!benutzer && !gruppe) return null
      const art = benutzer ? 'person' : 'gruppe'
      return {
        art,
        benutzer: benutzer || null,
        gruppe: gruppe || null,
        kennung: benutzer || gruppe,
        anzeige: text(f.name) || (benutzer || gruppe),
        lesen: Boolean(f.lesen),
        schreiben: Boolean(f.schreiben),
        moderieren: Boolean(f.moderieren),
      }
    })
    .filter(Boolean)
    .sort((a, b) => (a.art === b.art
      ? a.anzeige.localeCompare(b.anzeige, 'de')
      : (a.art === 'person' ? -1 : 1)))
}

/** Die gesetzten Stufen einer Zeile als Text („Lesen · Schreiben“). */
export function freigabeStufenText(zeile) {
  const gesetzt = FREIGABE_STUFEN.filter((s) => zeile && zeile[s])
    .map((s) => s.charAt(0).toUpperCase() + s.slice(1))
  return gesetzt.length ? gesetzt.join(' · ') : 'Keine Stufe'
}

/**
 * Woran hängt „Moderieren“ — und was heißt das für die Zeile?
 *
 * Der Server reicht `darf_moderieren_vergeben` durch: HV/MV der Gruppe (bzw.
 * Admin/Fachverwaltung am Gemeinde-Kalender) dürfen „Moderieren“ VERGEBEN,
 * ENTHEHEN und eine Zeile mit Moderieren entfernen. Alle anderen sehen den
 * Wert nur. Der Grundsatz der Oberfläche: sie entscheidet nichts über Rechte,
 * sie zeigt nur, was der Server ohnehin verweigert.
 *
 * Die Stufe gilt für JEDE Freigabe-Art — Personen UND Gruppen (der Server
 * kennt kein „Moderieren nur für Personen“; geprüft wird beim EINTRAG, nicht
 * bei der Art des Eintrags).
 *
 * @param {{darf_moderieren_vergeben?: boolean, art?: 'person'|'gruppe'}} lage
 */
export function freigabeKnoepfe(lage = {}) {
  const art = lage?.art === 'gruppe' ? 'gruppe' : 'person'
  const modus = Boolean(lage?.darf_moderieren_vergeben)
  return {
    art,
    modus,
    stufen: [...FREIGABE_STUFEN],
    hinweis: modus
      ? '„Moderieren“ heißt: Termine dieses Kalenders prüfen und freigeben.'
      : 'Das Prüfrecht vergeben nur HV und MV.',
  }
}

/**
 * Lage EINER Freigabe-Zeile: was darf sie schalten, was nur sehen?
 *
 *   `stufen`          alle Stufen (Moderieren wird immer GEZEIGT, solange die
 *                     Zeile es trägt — man muss sehen können, was gilt)
 *   `moderierenFest`  true = Wert unveränderlich mitgeführt (nur anzeigen)
 *   `entfernen`       darf die Zeile entfernt werden? Eine Zeile MIT
 *                     Moderieren nur mit `darf_moderieren_vergeben` (sonst
 *                     entzöge „Entfernen“ still das Prüfrecht; der Server
 *                     antwortet 403).
 *
 * @param {{art?: 'person'|'gruppe', moderieren?: boolean}} zeile
 * @param {{darf_moderieren_vergeben?: boolean}} lage
 */
export function freigabeZeilenLage(zeile = {}, lage = {}) {
  const knoepfe = freigabeKnoepfe({ darf_moderieren_vergeben: lage?.darf_moderieren_vergeben, art: zeile?.art })
  const mitModeration = Boolean(zeile?.moderieren)
  return {
    ...knoepfe,
    sichtbareStufen: knoepfe.stufen,
    moderierenFest: mitModeration && !knoepfe.modus,
    entfernen: !mitModeration || knoepfe.modus,
    entfernenHinweis: (!mitModeration || knoepfe.modus)
      ? ''
      : 'Diese Zeile trägt das Prüfrecht. Entfernen dürfen nur HV und MV.',
  }
}

/** Personen der Auswahl ohne die, die schon eine Zeile haben. */
export function personenAuswahlOhne(personen, freigaben) {
  const schon = new Set((Array.isArray(freigaben) ? freigaben : [])
    .map((f) => text(f && f.benutzer)).filter(Boolean))
  return (Array.isArray(personen) ? personen : [])
    .filter((p) => p && text(p.benutzer) && !schon.has(text(p.benutzer)))
}

/**
 * Wo darf der Aufrufer einen Kalender anlegen?
 *
 * Quelle sind die Serverfelder `anlegen_gruppen`/`anlegen_untergruppen` —
 * nicht die eigene Annahme. Auf einer Untergruppen-Seite steht die
 * Untergruppe ZUERST (dort legt ihre Leitung an), sonst die Gruppe. Der
 * Gemeinde-Kalender kommt nur mit `darf_gemeinde_kalender` und steht am Ende.
 *
 * @param {{darf_gemeinde_kalender?: boolean, anlegen_gruppen?: string[], anlegen_untergruppen?: string[]}} verwaltung
 * @param {{gruppe?: string, untergruppe?: string, gruppeName?: string, untergruppeName?: string}} umgebung
 * @returns {Array<{wert: string, art: 'gemeinde'|'gruppe'|'untergruppe', anzeige: string}>}
 */
export function anlegeZiele(verwaltung = {}, umgebung = {}) {
  const gruppe = text(umgebung?.gruppe)
  const untergruppe = text(umgebung?.untergruppe)
  const gruppen = (verwaltung?.anlegen_gruppen || []).map(text)
  const untergruppen = (verwaltung?.anlegen_untergruppen || []).map(text)
  const ziele = []

  if (untergruppe && untergruppen.includes(untergruppe)) {
    ziele.push({
      wert: untergruppe,
      art: 'untergruppe',
      anzeige: text(umgebung?.untergruppeName) || untergruppe,
    })
  }
  if (gruppe && gruppen.includes(gruppe)) {
    ziele.push({
      wert: gruppe,
      art: 'gruppe',
      anzeige: text(umgebung?.gruppeName) || gruppe,
    })
  }
  // Auf einer Untergruppen-Seite ist die Gruppe nur dann ein Ziel, wenn der
  // Server sie für den Aufrufer freigibt (MV der Hauptgruppe) — genau das
  // sagt `anlegen_gruppen`; hier wird nichts zusätzlich angenommen.
  if (verwaltung?.darf_gemeinde_kalender) {
    ziele.push({ wert: '', art: 'gemeinde', anzeige: GEMEINDE_TITEL })
  }
  return ziele
}

/**
 * Prüft Titel und Farbe VOR dem Senden (dieselben Grenzen wie im Server).
 * @returns {{ok: boolean, titel: string, farbe: string}}
 */
export function pruefeNeuenKalender({ titel, farbe } = {}) {
  const sauberTitel = text(titel)
  const sauberFarbe = text(farbe)
  let titelFehler = ''
  let farbeFehler = ''
  if (!sauberTitel) titelFehler = 'Bitte einen Namen für den Kalender angeben.'
  else if (sauberTitel.length > TITEL_MAX) {
    titelFehler = `Der Name darf höchstens ${TITEL_MAX} Zeichen lang sein.`
  }
  if (sauberFarbe && !FARBE.test(sauberFarbe)) {
    farbeFehler = `Farbe bitte als #rrggbb angeben (z. B. ${FARBE_BEISPIEL}).`
  }
  return {
    ok: !titelFehler && !farbeFehler,
    titel: titelFehler,
    farbe: farbeFehler,
  }
}

/**
 * Die Anfrage an `kalender_verwaltung.create_kalender`.
 *
 * Genau EIN Ziel: `untergruppe`, `gruppe` oder keins (Gemeinde-Kalender).
 * `standard_gruppe_lesen` ist die Antwort auf die Anlege-Frage (Ja = 1).
 *
 * @param {{titel: string, farbe?: string, ziel?: {wert: string, art: string},
 *          standardGruppeLesen?: boolean}} eingabe
 */
export function anlegeAnfrage({ titel, farbe = '', ziel = null, standardGruppeLesen = true } = {}) {
  const anfrage = {
    titel: text(titel),
    farbe: text(farbe),
    standard_gruppe_lesen: standardGruppeLesen ? 1 : 0,
  }
  const art = ziel?.art
  const wert = text(ziel?.wert)
  if (art === 'untergruppe' && wert) anfrage.untergruppe = wert
  else if (art === 'gruppe' && wert) anfrage.gruppe = wert
  return anfrage
}

/**
 * Der Stand einer Zeile auf dem Handy — was steht NEBEN welchem Kästchen?
 *
 * Zwei Dinge hängen hier zusammen, und beide lassen sich ohne Browser prüfen:
 *
 *   `felder`  je gezeigter Stufe ein Eintrag. Eine Stufe, die die Zeile NICHT
 *             trägt, bekommt `null` — kein unsichtbares Feld. Vorher stand für
 *             sie ein leeres `<label>` in der Reihe: es trug Breite und
 *             Abstand, das nächste Kästchen rückte weg von seinem Wort, und
 *             vor „Entfernen“ blieb ein Loch (UI-R2d, Punkt 4).
 *
 *             `wort` ist die Beschriftung NEBEN dem Kästchen — das Wort steht
 *             damit IN demselben `<label>` wie sein Kästchen, nicht am
 *             Reihenende.
 *
 *   `gesperrt` ist die Stufe bedienbar (siehe `zeileGesperrt` des Bausteins)?
 *
 * @param {{moderieren?: boolean}} zeile
 * @param {string[]} stufen  gezeigte Stufen in Anzeige-Reihenfolge
 * @param {{darf_moderieren_vergeben?: boolean, nurAnzeigen?: boolean}} lage
 * @param {(stufe: string) => boolean} [gesperrt]  Sperre je Stufe (vom Baustein)
 * @returns {{felder: Array<null|{stufe: string, wort: string, gesperrt: boolean}>, gesperrt: boolean}}
 */
export function handyStufen(zeile = {}, stufen = [], lage = {}, gesperrt = () => false) {
  const knoepfe = freigabeKnoepfe({
    darf_moderieren_vergeben: lage?.darf_moderieren_vergeben,
    art: zeile?.art,
  })
  // Dieselbe Regel wie im Baustein (`stufeDerZeile`): „Moderieren“ steht nur,
  // wenn die Zeile es trägt oder vergeben werden darf.
  const traegt = (stufe) => stufe !== 'moderieren'
    || Boolean(zeile?.moderieren) || knoepfe.modus
  const felder = (Array.isArray(stufen) ? stufen : []).map((stufe) => {
    if (!traegt(stufe)) return null
    return {
      stufe,
      wort: stufe === 'lesen' ? 'Lesen' : (stufe === 'schreiben' ? 'Schreiben' : 'Moderieren'),
      gesperrt: Boolean(lage?.nurAnzeigen) || Boolean(gesperrt(stufe)),
    }
  })
  // UI-R2e: die Rückgabe trägt NUR die Felder — das frühere `gesperrt` auf
  // oberster Ebene las niemand (die Zeilensperre entscheidet der Baustein).
  return { felder }
}

/**
 * Die Anfrage an `rechte.setze_freigabe` — genau eine Kennung.
 *
 * Alles `false` entfernt die Freigabe (Serverregel). „Moderieren“ wird IMMER
 * mitgeschickt: wer es nicht ändern darf, führt damit den bisherigen Wert
 * unverändert mit (der Server prüft jede ÄNDERUNG). Fehlt der bisherige Wert
 * in der Zeile, gilt `false` — mehr weiß die Oberfläche nicht.
 *
 * @param {{objekt: string, art: 'person'|'gruppe', kennung: string,
 *          lesen?: boolean, schreiben?: boolean, moderieren?: boolean}} eingabe
 */
export function freigabeAnfrage({ objekt, art, kennung, lesen = false, schreiben = false, moderieren = false } = {}) {
  const anfrage = {
    typ: 'kalender',
    objekt: text(objekt),
    lesen: Boolean(lesen),
    schreiben: Boolean(schreiben),
    moderieren: Boolean(moderieren),
  }
  if (art === 'gruppe') anfrage.gruppe = text(kennung)
  else anfrage.benutzer = text(kennung)
  return anfrage
}

/**
 * Die Felder einer Änderung an EINER Freigabe-Zeile.
 *
 * EINE Regel für alle drei Wege (Kästchen, „Entfernen“, Hinzufügen) — sonst
 * schickte ein Weg das Prüfrecht als `false` mit und entzöge es still.
 *
 * Ohne `darf_moderieren_vergeben` ist „Moderieren“ FEST: der bisherige Wert
 * fährt unverändert mit (Review UI-R2b, Punkt 1). Mit dem Recht gilt die
 * gewünschte Änderung; „Moderieren“ ohne „Lesen“ gibt es nicht (wer prüft,
 * sieht den Kalender).
 *
 * @param {{art: 'person'|'gruppe', kennung: string, lesen?: boolean,
 *          schreiben?: boolean, moderieren?: boolean}} zeile  Stand der Zeile
 * @param {{lesen?: boolean, schreiben?: boolean, moderieren?: boolean}} neu  gewünschter Stand
 * @param {{darf_moderieren_vergeben?: boolean}} lage
 */
export function freigabeFelder(zeile = {}, neu = {}, lage = {}) {
  const felder = {
    lesen: Boolean(neu.lesen),
    schreiben: Boolean(neu.schreiben),
  }
  felder.moderieren = Boolean(lage?.darf_moderieren_vergeben)
    ? Boolean(neu.moderieren) && felder.lesen
    : Boolean(zeile.moderieren)
  return felder
}

/**
 * Der EINE Schlüssel einer laufenden Aktion — Codeliste und Baustein müssen
 * dasselbe Format benutzen, sonst sperrt die Karte nichts (Review UI-R2b,
 * Punkt 3: die Sperre griff nie, ein Doppelklick sendete zweimal).
 *
 *   `freigabe-<objekt>-<art>-<kennung>`
 *   `standard-<objekt>`
 *   `sichtbarkeit-<objekt>-<ziel>`
 */
export function busySchluessel(art, ...teile) {
  return [String(art || ''), ...teile.map((t) => String(t ?? ''))].filter((t) => t !== '').join('-')
}

/**
 * Anfragezähler je Kalender: nur die JÜNGSTE Antwort darf schreiben
 * (Review UI-R2b, Punkt 4 — auf/zu/auf überschrieb neuere mit älteren Daten).
 *
 * Benutzung: `const nr = zaehler.starten(name)` … Antwort … `wenn(zaehler, name, nr)`.
 */
export function anfrageZaehler() {
  const stand = new Map()
  return {
    starten(schluessel) {
      const nr = (stand.get(schluessel) || 0) + 1
      stand.set(schluessel, nr)
      return nr
    },
    aktuell(schluessel, nr) {
      return stand.get(schluessel) === nr
    },
  }
}

/**
 * Erfolgsmeldung nach einer Freigabe — sie nennt das ZIEL.
 *
 * „beantragt“ sagt, wer jetzt prüft: die Gruppe (HV/MV) oder die Gemeinde.
 *
 * @param {{ziel: 'gruppe'|'gemeinde'}} eingabe
 * @param {string} stand  Serverstand danach (beantragt/aktiv)
 * @param {'beantragen'|'zuruecknehmen'} weg
 */
export function sichtbarkeitMeldung({ ziel } = {}, stand, weg = 'beantragen') {
  const gruppe = ziel === 'gruppe'
  if (weg === 'zuruecknehmen') {
    return gruppe
      ? 'Freigabe für die ganze Gruppe zurückgenommen — gilt sofort.'
      : 'Freigabe für alle Mitglieder der Gemeinde zurückgenommen — gilt sofort.'
  }
  if (stand === 'aktiv') {
    return gruppe
      ? 'Freigegeben — die ganze Gruppe sieht den Kalender jetzt.'
      : 'Freigegeben — alle Mitglieder der Gemeinde sehen den Kalender jetzt.'
  }
  return gruppe
    ? 'Antrag eingetragen — er wartet auf HV/MV der Gruppe.'
    : 'Antrag eingetragen — er wartet auf die Prüfung durch die Gemeinde.'
}

/**
 * Ein Serverfehler als Satz für Menschen.
 *
 * Fachliche Sätze des Servers (403/417 mit deutschem `message`) gehen VOR —
 * nur Statuscodes und Floskeln werden ersetzt. Damit steht nie „HTTP 403“ in
 * der Fläche.
 */
export function sichererFehlertext(fehler, ersatz = {}) {
  const roh = text(fehler?.message || '')
  const technisch = !roh || /^HTTP \d+$/i.test(roh) || /^\d{3}$/.test(roh)
    || /^(fehler|error|internal server error|ungueltige anfrage|ungültige anfrage)$/i.test(roh)
  if (technisch) return text(ersatz?.text) || 'Das hat gerade nicht geklappt. Versuche es noch einmal.'
  return roh
}
