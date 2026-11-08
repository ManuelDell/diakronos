<section class="dk-steckbrief" lang="de">
  {#if ladezustand === "laedt"}
    {#if ueberschrift}<h2 class="dk-steckbrief__titel">{ueberschrift}</h2>{/if}
    <p class="dk-steckbrief__hinweis" role="status">{text_laedt}</p>
  {:else if ladezustand === "fehler"}
    {#if ueberschrift}<h2 class="dk-steckbrief__titel">{ueberschrift}</h2>{/if}
    <p class="dk-steckbrief__hinweis" role="status">{fehlertext}</p>
  {:else if befund === null}
    {#if ueberschrift}<h2 class="dk-steckbrief__titel">{ueberschrift}</h2>{/if}
    <p class="dk-steckbrief__hinweis" role="status">{leertext}</p>
  {:else}
    <div class="dk-steckbrief__rumpf" aria-live="polite">
      {#if befund.bild_url}
        <!-- BS-2c2 (3): dekoratives Bild. Der Name der Gruppe steht direkt
             daneben als Ueberschrift — ein Alt-Text mit demselben Wort liest
             sich fuer Screenreader doppelt. `alt=""` nimmt das Bild aus dem
             Namensbaum; ein KNOPF ist es nicht, es geht also kein Bedienelement
             verloren. (Ein `<figure><figcaption>` waere fuer ein INHALTLICHES
             Bild richtig — das Gruppenbild ist Schmuck.) -->
        <img class="dk-steckbrief__bild" src={befund.bild_url} alt="" loading="lazy" decoding="async" />
      {/if}
      <div class="dk-steckbrief__inhalt">
        <h2 class="dk-steckbrief__titel">{titel_anzeige}</h2>
        {#if befund.typ}<p class="dk-steckbrief__typ">{befund.typ}</p>{/if}
        {#if befund.beschreibung}<p class="dk-steckbrief__beschreibung">{befund.beschreibung}</p>{/if}

        {#if befund.treffzeit || befund.treffpunkt}
          <dl class="dk-steckbrief__daten">
            {#if befund.treffzeit}
              <div class="dk-steckbrief__paar">
                <dt class="dk-steckbrief__wort">{text_treffzeit}</dt>
                <dd class="dk-steckbrief__wert">{befund.treffzeit}</dd>
              </div>
            {/if}
            {#if befund.treffpunkt}
              <div class="dk-steckbrief__paar">
                <dt class="dk-steckbrief__wort">{text_treffpunkt}</dt>
                <dd class="dk-steckbrief__wert">{befund.treffpunkt}</dd>
              </div>
            {/if}
          </dl>
        {/if}

        {#if kontakt_hinweis}
          <p class="dk-steckbrief__kontakt">{kontakt_hinweis}</p>
        {/if}
      </div>
    </div>

    {#if anzahl >= 1}
      <h3 class="dk-steckbrief__termine-titel">{text_termine}</h3>
      {#if befund.termine.length === 0}
        <p class="dk-steckbrief__hinweis">{leertext_termine}</p>
      {:else}
        <ul class="dk-steckbrief__termine">
          {#each befund.termine as termin (termin.id)}
            <li class="dk-steckbrief__termin">
              <p class="dk-steckbrief__wann">
                <span class="dk-steckbrief__tag">{termin.tag}</span>
                {#if termin.uhrzeit}<span class="dk-steckbrief__uhr">{termin.uhrzeit}</span>{/if}
              </p>
              <p class="dk-steckbrief__was">
                <span class="dk-steckbrief__name">{termin.titel}</span>
                {#if termin.ort}<span class="dk-steckbrief__wo">{termin.ort}</span>{/if}
              </p>
            </li>
          {/each}
        </ul>
      {/if}
    {/if}
  {/if}
</section>

<script>
  // Abschnitte sind SERVER-Komponenten: Primo rendert mit `svelte/server`,
  // `onMount` ist dort verboten (der Publish bricht ab). Der Abruf steht
  // deshalb in `$effect` (bei SSR inaktiv, im Browser einmal beim Einhaengen).
  // `gruppe` ist hier der NAME des Feldes "Kennung der Gruppe" und zugleich
  // der Zustand der geladenen Gruppe — deshalb heisst der Zustand `befund`.

  let {
    ueberschrift = '',
    basisadresse = '',
    gruppe = '',
    anzahl_termine = 3,
    kontakt_hinweis = '',
    text_treffzeit = 'Treffzeit',
    text_treffpunkt = 'Treffpunkt',
    text_termine = 'Nächste Termine',
    text_ganztaegig = 'ganztägig',
    text_laedt = 'Steckbrief wird geladen …',
    leertext = 'Zu dieser Gruppe sind zurzeit keine Angaben veröffentlicht.',
    leertext_termine = 'Zurzeit sind keine Termine angekündigt.',
    fehlertext = 'Der Steckbrief ist derzeit nicht abrufbar. Bitte später erneut versuchen.'
  } = $props();

  /** @type {'laedt' | 'fertig' | 'fehler'} */
  let ladezustand = $state('laedt');
  /** @type {null | {name: string, typ: string, beschreibung: string, treffzeit: string, treffpunkt: string, bild_url: string, termine: Array<any>}} */
  let befund = $state(null);

  const ZEITLIMIT_MS = 8000;
  const ZEITZONE = 'Europe/Berlin';

  let titel_anzeige = $derived(String(ueberschrift || '').trim() !== '' ? String(ueberschrift).trim() : (befund === null ? '' : befund.name));
  let anzahl = $derived(zahl(anzahl_termine, 3, 0, 20));

  // ── Hilfslogik: Adressen ────────────────────────────────────────────────
  // Bewusst eigenstaendig (README Regel 1: keine Importe zwischen Bausteinen).
  function nur_webadresse(wert) {
    const text = String(wert || '').trim();
    if (!/^https?:\/\//i.test(text)) return '';
    const ohne_schraegstrich = text.replace(/\/+$/, '');
    try {
      const geprueft = new URL(ohne_schraegstrich);
      return geprueft.protocol === 'http:' || geprueft.protocol === 'https:' ? ohne_schraegstrich : '';
    } catch (fehler) {
      return '';
    }
  }

  function basis() {
    return nur_webadresse(basisadresse);
  }

  /**
   * Praefixbewusste, moeglicherweise relative Bildadresse absolut machen.
   *
   * Die Lese-API liefert Bildadressen MIT Betriebspraefix
   * (`/diakronos/website/bild/gruppe/chor`, gebaut aus DIAKRONOS_BASE_PATH).
   * Die Basisadresse im Feld traegt dasselbe Praefix
   * (`…/diakronos`) — blindes Anhaengen ergaebe `…/diakronos/diakronos/…`
   * (404). Deshalb: steckt das Praefix der Basis schon am Anfang des Pfades,
   * wird die Adresse unveraendert uebernommen (BS-2c2; derselbe Befund wie
   * beim Anmelde-Knopf in BS-2c).
   */
  function bild_adresse(wert) {
    const text = String(wert || '').trim();
    if (text === '') return '';
    if (/^https?:\/\//i.test(text)) return nur_webadresse(text);
    const basiswert = basis();
    if (basiswert === '' || !text.startsWith('/')) return '';
    let praefix = '';
    try {
      praefix = new URL(basiswert).pathname.replace(/\/+$/, '');
    } catch (fehler) {
      praefix = '';
    }
    if (praefix !== '' && praefix !== '/' && text.startsWith(praefix + '/')) {
      return basiswert.slice(0, basiswert.length - praefix.length) + text;
    }
    return basiswert + text;
  }

  // ── Hilfslogik: Datum/Uhrzeit in Europe/Berlin ──────────────────────────
  const WOCHENTAGE = ['So', 'Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa'];

  function als_datum(wert) {
    const text = String(wert || '').trim();
    if (text === '') return null;
    const datum = new Date(text);
    return Number.isNaN(datum.getTime()) ? null : datum;
  }

  function teile(datum) {
    const formatter = new Intl.DateTimeFormat('de-DE', {
      timeZone: ZEITZONE,
      year: 'numeric',
      month: '2-digit',
      day: '2-digit'
    });
    const stuecke = formatter.formatToParts(datum);
    const wert = (art) => (stuecke.find((s) => s.type === art) || {}).value || '';
    return { tag: wert('day'), monat: wert('month'), jahr: wert('year') };
  }

  /** "Sa., 08.11." — Wochentag in der Zeitzone der Gemeinde. */
  function tagestext(datum) {
    const wochentag = new Intl.DateTimeFormat('de-DE', {
      timeZone: ZEITZONE,
      weekday: 'short'
    }).format(datum);
    const { tag, monat } = teile(datum);
    return wochentag.replace(/\.$/, '') + '., ' + tag + '.' + monat + '.';
  }

  function isodatum(datum) {
    const { tag, monat, jahr } = teile(datum);
    return jahr + '-' + monat + '-' + tag;
  }

  /** "Sa., 08.11. – So., 09.11." — leer, wenn eintaegig (F1-Regel BS-2a). */
  function ende_text(beginn, ende) {
    const ende_datum = als_datum(ende);
    if (ende_datum === null) return '';
    if (isodatum(beginn) === isodatum(ende_datum)) return '';
    return tagestext(ende_datum);
  }

  function uhrzeittext(datum) {
    const stuecke = new Intl.DateTimeFormat('de-DE', {
      timeZone: ZEITZONE,
      hour: '2-digit',
      minute: '2-digit',
      hourCycle: 'h23'
    }).formatToParts(datum);
    const wert = (art) => (stuecke.find((s) => s.type === art) || {}).value || '';
    return wert('hour') + ':' + wert('minute');
  }

  function zeitfenster(beginn, ende) {
    const start = als_datum(beginn);
    if (start === null) return '';
    const ende_datum = als_datum(ende);
    if (ende_datum === null) return uhrzeittext(start);
    if (isodatum(start) !== isodatum(ende_datum)) return uhrzeittext(start);
    return uhrzeittext(start) + ' – ' + uhrzeittext(ende_datum);
  }

  function zahl(wert, vorgabe, minimum, maximum) {
    const geprueft = Number(String(wert === null || wert === undefined ? '' : wert).replace(',', '.'));
    if (!Number.isFinite(geprueft)) return vorgabe;
    return Math.min(maximum, Math.max(minimum, Math.trunc(geprueft)));
  }

  // ── Daten holen ─────────────────────────────────────────────────────────
  function abfrageadresse() {
    const basiswert = basis();
    const kennung = String(gruppe || '').trim();
    if (basiswert === '' || kennung === '') return '';
    const parameter = new URLSearchParams();
    parameter.set('slug', kennung);
    return basiswert + '/website/oeffentlich/gruppe?' + parameter.toString();
  }

  /** Termine der Antwort -> Anzeigezeilen (Feld-Positivliste der API). */
  function termin_zeilen(daten) {
    const liste = Array.isArray(daten) ? daten : [];
    const ergebnis = [];
    for (const eintrag of liste) {
      if (!eintrag || typeof eintrag !== 'object') continue;
      const beginn = als_datum(eintrag.beginn);
      if (beginn === null) continue;
      const zeit = eintrag.ganztaegig === true ? '' : zeitfenster(eintrag.beginn, eintrag.ende);
      const zeitraum = ende_text(beginn, eintrag.ende);
      ergebnis.push({
        id: String(eintrag.id || '') || tagestext(beginn) + String(eintrag.titel || ''),
        tag: tagestext(beginn) + (zeitraum !== '' ? ' – ' + zeitraum : ''),
        uhrzeit: zeit === '' && eintrag.ganztaegig === true ? text_ganztaegig : zeit,
        titel: String(eintrag.titel || '').trim(),
        ort: String(eintrag.ort || '').trim()
      });
    }
    return ergebnis;
  }

  function befund_aus_antwort(daten) {
    if (!daten || typeof daten !== 'object' || Array.isArray(daten)) return null;
    const name = String(daten.name || '').trim();
    const beschreibung = String(daten.beschreibung || '').trim();
    const termm = termin_zeilen(daten.naechste_termine);
    // Eine Gruppe ohne Name und ohne Beschreibung ist zwar freigegeben, aber
    // ohne Inhalt — dann ist der Leertext ehrlicher als eine leere Karte.
    const typ = String(daten.typ || '').trim();
    const treffzeit = String(daten.treffzeit || '').trim();
    const treffpunkt = String(daten.treffpunkt || '').trim();
    const bild_url = bild_adresse(daten.bild_url);
    if (name === '' && beschreibung === '' && typ === '' && treffzeit === ''
        && treffpunkt === '' && bild_url === '' && termm.length === 0) {
      return null;
    }
    return {
      name,
      typ,
      beschreibung,
      treffzeit,
      treffpunkt,
      bild_url,
      termine: anzahl >= 1 ? termm.slice(0, anzahl) : []
    };
  }

  async function laden() {
    const adresse = abfrageadresse();
    if (adresse === '') {
      // Ohne Kennung/Adresse gibt es nichts abzurufen: Konfigurationsfehler
      // des Redakteurs. Gleiche Anzeige wie ein Ladefehler, ohne Netzzugriff.
      ladezustand = 'fehler';
      return;
    }
    const abbruch = typeof AbortController === 'function' ? new AbortController() : null;
    const wecker = abbruch === null ? null : setTimeout(() => abbruch.abort(), ZEITLIMIT_MS);
    try {
      const antwort = await fetch(adresse, {
        method: 'GET',
        mode: 'cors',
        credentials: 'omit',
        cache: 'no-store',
        headers: { Accept: 'application/json' },
        signal: abbruch === null ? undefined : abbruch.signal
      });
      // 404 = nicht freigegeben oder unbekannt. Die API verraet den
      // Unterschied nicht — der Block zeigt den Leertext, nicht den Fehler.
      if (antwort.status === 404) {
        befund = null;
        ladezustand = 'fertig';
        return;
      }
      if (!antwort.ok) throw new Error('HTTP ' + antwort.status);
      const koerper = await antwort.json();
      if (!koerper || typeof koerper !== 'object' || !('message' in koerper)) {
        throw new Error('Antwortform');
      }
      befund = befund_aus_antwort(koerper.message);
      ladezustand = 'fertig';
    } catch (fehler) {
      // Kein Inhalt in die Konsole: der Block zeigt den Fehler selbst an.
      befund = null;
      ladezustand = 'fehler';
    } finally {
      if (wecker !== null) clearTimeout(wecker);
    }
  }

  $effect(() => {
    laden();
  });
</script>

<style>
  /* --dk-* NUR LESEN, nie deklarieren (BS-0 F5). Vorgaben nur als
     var()-Fallback. Dunkelmodus: alles erbt von der Site. */
  .dk-steckbrief {
    color: var(--dk-farbe-text, inherit);
    background: var(--dk-farbe-flaeche, transparent);
    font-family: var(--dk-schrift, inherit);
    font-size: var(--dk-groesse-text, 1rem);
    box-sizing: border-box;
    padding: var(--dk-abstand, 0.75rem) 0;
    border-top: var(--dk-rahmen-breite, 1px) solid
      var(--dk-farbe-rahmen, color-mix(in srgb, currentColor 25%, transparent));
  }

  .dk-steckbrief *,
  .dk-steckbrief *::before,
  .dk-steckbrief *::after {
    box-sizing: border-box;
  }

  .dk-steckbrief__rumpf {
    display: flex;
    flex-direction: column;
    gap: var(--dk-abstand, 0.75rem);
  }

  .dk-steckbrief__bild {
    display: block;
    width: 100%;
    height: auto;
    aspect-ratio: 3 / 2;
    object-fit: cover;
    border-radius: var(--dk-rahmen-radius, 0.5rem);
  }

  .dk-steckbrief__inhalt {
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
    min-width: 0;
  }

  .dk-steckbrief__titel,
  .dk-steckbrief__termine-titel {
    margin: 0;
    font-family: var(--dk-schrift-ueberschrift, var(--dk-schrift, inherit));
    line-height: 1.25;
    color: var(--dk-farbe-ueberschrift, inherit);
  }

  .dk-steckbrief__titel {
    font-size: var(--dk-groesse-ueberschrift, 1.375rem);
  }

  .dk-steckbrief__termine-titel {
    font-size: 1.125rem;
    margin: var(--dk-abstand, 0.75rem) 0 0.35rem;
  }

  .dk-steckbrief__typ,
  .dk-steckbrief__hinweis {
    margin: 0;
    font-size: var(--dk-groesse-klein, 0.875rem);
    color: var(--dk-farbe-gedaempft, color-mix(in srgb, currentColor 70%, transparent));
  }

  .dk-steckbrief__beschreibung {
    margin: 0;
    white-space: pre-line;
    overflow-wrap: anywhere;
  }

  .dk-steckbrief__daten {
    margin: 0;
    display: grid;
    gap: 0.25rem;
    font-size: var(--dk-groesse-klein, 0.875rem);
  }

  .dk-steckbrief__paar {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
  }

  .dk-steckbrief__wort {
    margin: 0;
    font-weight: 600;
  }

  .dk-steckbrief__wert {
    margin: 0;
    color: var(--dk-farbe-gedaempft, color-mix(in srgb, currentColor 70%, transparent));
  }

  .dk-steckbrief__kontakt {
    margin: 0;
    padding: var(--dk-abstand-klein, 0.5rem) var(--dk-abstand, 0.75rem);
    border-left: 3px solid var(--dk-farbe-akzent, color-mix(in srgb, currentColor 45%, transparent));
    border-radius: var(--dk-rahmen-radius, 0.25rem);
    white-space: pre-line;
    overflow-wrap: anywhere;
  }

  .dk-steckbrief__termine {
    margin: 0;
    padding: 0;
    list-style: none;
  }

  .dk-steckbrief__termin {
    display: flex;
    flex-direction: column;
    gap: 0.1rem;
    padding: var(--dk-abstand-klein, 0.5rem) 0;
    border-bottom: var(--dk-rahmen-breite, 1px) solid
      var(--dk-farbe-rahmen, color-mix(in srgb, currentColor 25%, transparent));
  }

  .dk-steckbrief__termin:last-child {
    border-bottom: 0;
  }

  .dk-steckbrief__wann {
    margin: 0;
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    font-size: var(--dk-groesse-klein, 0.875rem);
    color: var(--dk-farbe-gedaempft, color-mix(in srgb, currentColor 70%, transparent));
  }

  .dk-steckbrief__tag,
  .dk-steckbrief__name {
    font-weight: 600;
  }

  .dk-steckbrief__was {
    margin: 0;
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    align-items: baseline;
  }

  .dk-steckbrief__wo {
    font-size: var(--dk-groesse-klein, 0.875rem);
    color: var(--dk-farbe-gedaempft, color-mix(in srgb, currentColor 70%, transparent));
  }

  @media (min-width: 40em) {
    .dk-steckbrief__rumpf {
      flex-direction: row;
      align-items: flex-start;
    }

    .dk-steckbrief__bild {
      width: 40%;
      max-width: 22rem;
      flex: 0 0 auto;
    }

    .dk-steckbrief__inhalt {
      flex: 1 1 auto;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .dk-steckbrief * {
      transition: none !important;
      animation: none !important;
    }
  }
</style>
