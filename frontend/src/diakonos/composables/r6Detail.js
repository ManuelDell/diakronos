/**
 * R6 — Welcher Eintrag steht im Detail-Dialog?
 *
 * EINE Regel für Beiträge und Wiki-Artikel (Review-Befund 12.11., Punkt 1):
 *
 * Die LISTE trägt je Eintrag `darf_bearbeiten`. Bis UI-R6d tat das DETAIL
 * (`get_beitrag_detail`, `get_wiki_artikel_detail`) es NICHT — wer dort einfach
 * die Detailantwort nahm, verlor das Recht und damit „Für Gäste
 * freigeben“/„Bearbeiten“/„Löschen“.
 *
 * Seit R-12l (UI-R6e) liefern BEIDE Detail-Aufrufe `darf_bearbeiten` selbst;
 * die Leseseiten nehmen es direkt aus dem Detail. `detailMitListe` bleibt für
 * Aufrufer, die Detail- und Listenwerte zusammenlegen müssen.
 *
 * Deshalb: Detailwerte ÜBER den Listeneintrag legen (der Listeneintrag bleibt
 * der Grundstand). Was das Detail NEU mitbringt (Inhalt, Kommentare), gewinnt;
 * was es NICHT liefert (`darf_bearbeiten`, `image`, `excerpt`), bleibt erhalten.
 *
 * Der Server entscheidet weiter allein: hier wird nichts bejaht oder verneint,
 * nur zusammengelegt.
 */

/**
 * @param {object|null} eintrag  Listeneintrag (trägt `darf_bearbeiten`)
 * @param {object|null} detail   Antwort des Detailaufrufs
 * @returns {object|null} Grundstand aus der Liste, überschrieben vom Detail
 */
export function detailMitListe(eintrag, detail) {
    const liste = eintrag && typeof eintrag === 'object' ? eintrag : {}
    const fein = detail && typeof detail === 'object' ? detail : {}
    const zusammen = { ...liste, ...fein }
    // `undefined` im Detail darf einen guten Listenwert nicht wegwerfen:
    // sonst stünde `image: undefined` über `image: '…'` und die Gestalt kippte.
    for (const [schluessel, wert] of Object.entries(fein)) {
        if (wert === undefined && schluessel in liste) zusammen[schluessel] = liste[schluessel]
    }
    return zusammen
}

/** Hat der Server Bearbeiten erlaubt? (`darf_bearbeiten`, sonst nein.) */
export function darfBearbeiten(eintrag) {
    return eintrag?.darf_bearbeiten === true
}
