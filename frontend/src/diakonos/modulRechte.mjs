/**
 * CHAT-R2a-2 · Eine Modul-Regel für Router-Guard UND Fußleiste.
 *
 * Die Frage „darf diese Sitzung das Chat-Modul öffnen?“ stand bisher nur im
 * Router (`modulChatErlaubt`). Die Handy-Leiste braucht dieselbe Antwort — und
 * ein zweiter Nachbau der Bedingungen wäre genau die Sorte Kopie, die
 * auseinanderläuft (dann zeigt die Leiste einen Tab, den der Wächter
 * anschließend auf den Start zurückwirft: eine Sackgasse).
 *
 * Deshalb liegt die Regel hier, in einem Modul OHNE DOM- und ohne
 * Vue-Bezug: der Router importiert sie (und exportiert sie weiter, damit die
 * bestehenden Router-Tests sie an derselben Stelle finden), `fusstabs.mjs`
 * ebenso. Kein Zyklus, kein `window` beim Laden.
 */

/**
 * Darf diese Sitzung das Chat-Modul öffnen? (Chat-Konzept 10.2: „Modul `chat`
 * (`modul_aktiv`), sonst wie Chats heute“.)
 *
 * Die Regel ist die des Servers, nur gespiegelt: der Server listet in
 * `module_sichtbar` genau die Module auf, in denen die Sitzung etwas lesen darf
 * (`rechte.sichtbare_module`; Administrator: alle, Gast: keine). Dieselbe
 * Liste benutzt schon das Menü (`menue.js::bootModule`), deshalb steht hier
 * KEINE zweite Rechte-Geschichte — nur der Blick in das Boot-Objekt.
 *
 * Fail closed: fehlt die Liste (alter Server, Test ohne Boot), gilt das Modul
 * als NICHT freigegeben und die Seite bleibt zu. Ein Administrator
 * (`is_admin === true`) kommt durch — so rechnet es auch `_module_sichtbar` in
 * `spa.py`, und ein fehlendes Feld soll ihn nicht aus seinem eigenen Bereich
 * sperren.
 *
 * @param {{is_admin?: boolean, module_sichtbar?: string[]|null}} boot
 * @returns {boolean}
 */
export function modulChatErlaubt(boot = (typeof window === 'undefined' ? {} : (window.__DIakonosBOOT || {}))) {
    if (boot.is_admin === true) return true
    const liste = boot.module_sichtbar
    if (!Array.isArray(liste)) return false
    return liste.includes('chat')
}
