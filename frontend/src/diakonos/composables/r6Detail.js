/**
 * R6 — Darf der Aufrufer bearbeiten?
 *
 * EINE Regel für Beiträge und Wiki-Artikel (Review-Befund 12.11., Punkt 1):
 *
 * Die LISTE trägt je Eintrag `darf_bearbeiten`. Bis UI-R6d tat das DETAIL
 * (`get_beitrag_detail`, `get_wiki_artikel_detail`) es NICHT — wer dort einfach
 * die Detailantwort nahm, verlor das Recht und damit „Für Gäste
 * freigeben“/„Bearbeiten“/„Löschen“.
 *
 * Seit R-12l (UI-R6e) liefern BEIDE Detail-Aufrufe `darf_bearbeiten` selbst;
 * die Leseseiten nehmen es direkt aus dem Detail. Die frühere Zusammenlegung
 * von Listen- und Detailwerten (`detailMitListe`) hatte damit keinen Aufrufer
 * mehr und ist in AUFR-1 entfallen.
 *
 * Der Server entscheidet allein: hier wird nichts bejaht oder verneint.
 */

/** Hat der Server Bearbeiten erlaubt? (`darf_bearbeiten`, sonst nein.) */
export function darfBearbeiten(eintrag) {
    return eintrag?.darf_bearbeiten === true
}
