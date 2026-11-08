<section class="dk-gd" lang="de">
  <h2 class="dk-gd__titel">{ueberschrift}</h2>

  {#if ladezustand === 'laedt'}
    <p class="dk-gd__hinweis" role="status">{text_laedt}</p>
  {:else if ladezustand === 'fehler'}
    <p class="dk-gd__hinweis dk-gd__hinweis--fehler" role="status">{fehlertext}</p>
  {:else if !termin}
    <p class="dk-gd__hinweis" role="status">{leertext}</p>
  {:else}
    <article class="dk-gd__karte">
      <p class="dk-gd__wochentag">{termin.wochentag}</p>
      <p class="dk-gd__datum">
        <span class="dk-gd__tag">{termin.tag}</span>
        <span class="dk-gd__monat">{termin.monat}</span>
      </p>
      {#if termin.zeit}<p class="dk-gd__zeit">{termin.zeit}</p>{/if}
      <p class="dk-gd__was">{termin.titel}</p>
      {#if ort_anzeigen !== false && termin.ort}<p class="dk-gd__ort">{termin.ort}</p>{/if}
      {#if zusatztext}<p class="dk-gd__zusatz">{zusatztext}</p>{/if}
      {#if termin.link}
        <p class="dk-gd__link"><a class="dk-gd__link-a" href={termin.link} rel="noopener">{link_text || 'Livestream'}</a></p>
      {/if}
    </article>
  {/if}
</section>

<script>
  // BS-2b: wie „Nächste Termine" (BS-2a2) — Primo rendert Abschnitte als
  // SERVER-Komponente, der Abruf gehört deshalb in `$effect` (bei SSR aus,
  // im Browser einmal beim Einhängen).

  let {
    ueberschrift = 'Nächster Gottesdienst',
    basisadresse = '',
    auswahl = 'kalender',
    kalender = '',
    kategorie = '',
    zusatztext = '',
    link = '',
    link_text = 'Livestream',
    ort_anzeigen = true,
    leertext = 'Zurzeit ist kein Termin angekündigt.',
    text_laedt = 'Termin wird geladen …',
    fehlertext = 'Der Termin ist derzeit nicht abrufbar. Bitte später erneut versuchen.'
  } = $props();

  const ZEITZONE = 'Europe/Berlin';
  const ZEITLIMIT_MS = 8000;
  const MONATSNAMEN = ['Januar', 'Februar', 'März', 'April', 'Mai', 'Juni', 'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember'];
  const WOCHENTAGE_LANG = ['Sonntag', 'Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag'];

  /** @type {'laedt' | 'fertig' | 'fehler'} */
  let ladezustand = $state('laedt');
  /** @type {object | null} */
  let termin = $state(null);

  // Einmal gelesen (Vorgabefeld, kein Zustand) — danach fest.
  const KATEGORIE_AUSWAHL = String(auswahl || '').trim() === 'kategorie';

  // ── Hilfslogik (bewusst im Block: Primo kopiert Blöcke in Sites) ─────────
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

  function als_datum(wert) {
    const text = String(wert || '').trim();
    if (text === '') return null;
    const datum = new Date(text);
    return Number.isNaN(datum.getTime()) ? null : datum;
  }

  function teile(datum) {
    const stuecke = new Intl.DateTimeFormat('de-DE', {
      timeZone: ZEITZONE, year: 'numeric', month: '2-digit', day: '2-digit'
    }).formatToParts(datum);
    const wert = (art) => (stuecke.find((s) => s.type === art) || {}).value || '';
    return { tag: wert('day'), monat: wert('month'), jahr: wert('year') };
  }

  function isodatum(datum) {
    const { tag, monat, jahr } = teile(datum);
    return jahr + '-' + monat + '-' + tag;
  }

  function uhrzeittext(datum) {
    const stuecke = new Intl.DateTimeFormat('de-DE', {
      timeZone: ZEITZONE, hour: '2-digit', minute: '2-digit', hourCycle: 'h23'
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

  /** Wochentag, Tag, Monat und Zeit — alles in der Zeitzone der Gemeinde. */
  function anzeige(eintrag) {
    const beginn = als_datum(eintrag.beginn);
    if (beginn === null) return null;
    const iso = isodatum(beginn);
    const nummer = new Date(Date.UTC(Number(iso.slice(0, 4)), Number(iso.slice(5, 7)) - 1, Number(iso.slice(8, 10)))).getUTCDay();
    return {
      wochentag: WOCHENTAGE_LANG[nummer],
      tag: String(Number(iso.slice(8, 10))),
      monat: MONATSNAMEN[Number(iso.slice(5, 7)) - 1] + ' ' + iso.slice(0, 4),
      zeit: eintrag.ganztaegig === true ? '' : zeitfenster(eintrag.beginn, eintrag.ende),
      titel: String(eintrag.titel || '').trim(),
      ort: String(eintrag.ort || '').trim(),
      link: nur_webadresse(link)
    };
  }

  // ── Daten holen ─────────────────────────────────────────────────────────
  function abfrageadresse() {
    const basiswert = nur_webadresse(basisadresse);
    if (basiswert === '') return '';
    const parameter = new URLSearchParams();
    // Der Endpunkt liefert den nächsten TERMIN ab heute — der Zeitraum wird
    // hier nicht gebraucht (`naechster_termin` hat keine von/bis-Felder).
    const kategorie_wert = String(kategorie || '').trim();
    const kalender_wert = String(kalender || '').trim();
    if (KATEGORIE_AUSWAHL && kategorie_wert !== '') parameter.set('kategorie', kategorie_wert);
    if (!KATEGORIE_AUSWAHL && kalender_wert !== '') parameter.set('kalender', kalender_wert);
    const frage = parameter.toString();
    return basiswert + '/website/oeffentlich/naechster_termin' + (frage === '' ? '' : '?' + frage);
  }

  async function laden() {
    const adresse = abfrageadresse();
    if (adresse === '') {
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
      if (!antwort.ok) throw new Error('HTTP ' + antwort.status);
      const koerper = await antwort.json();
      if (!koerper || typeof koerper !== 'object' || !('message' in koerper)) throw new Error('Antwortform');
      const daten = koerper.message;
      termin = daten && typeof daten === 'object' ? anzeige(daten) : null;
      ladezustand = 'fertig';
    } catch (fehler) {
      termin = null;
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
  /* --dk-* nur lesen (BS-0 F5); Dunkelmodus: Farben erben (BS-2a „Weg 1"). */
  .dk-gd {
    color: var(--dk-farbe-text, inherit);
    background: var(--dk-farbe-flaeche, transparent);
    font-family: var(--dk-schrift, inherit);
    font-size: var(--dk-groesse-text, 1rem);
    box-sizing: border-box;
    padding: var(--dk-abstand, 0.75rem) 0;
    border-top: var(--dk-rahmen-breite, 1px) solid var(--dk-farbe-rahmen, color-mix(in srgb, currentColor 25%, transparent));
  }

  .dk-gd *,
  .dk-gd *::before,
  .dk-gd *::after {
    box-sizing: border-box;
  }

  .dk-gd__titel {
    margin: 0 0 var(--dk-abstand, 0.75rem);
    font-family: var(--dk-schrift-ueberschrift, var(--dk-schrift, inherit));
    font-size: var(--dk-groesse-ueberschrift, 1.375rem);
    line-height: 1.25;
  }

  .dk-gd__karte {
    border: var(--dk-rahmen-breite, 1px) solid var(--dk-farbe-rahmen, color-mix(in srgb, currentColor 25%, transparent));
    border-left: 0.35rem solid var(--dk-farbe-akzent, currentColor);
    border-radius: var(--dk-rahmen-radius, 0.375rem);
    padding: var(--dk-abstand, 0.75rem);
    display: flex;
    flex-direction: column;
    gap: 0.2rem;
  }

  .dk-gd__wochentag {
    margin: 0;
    font-size: var(--dk-groesse-klein, 0.875rem);
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--dk-farbe-gedaempft, color-mix(in srgb, currentColor 70%, transparent));
  }

  .dk-gd__datum {
    margin: 0;
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
    align-items: baseline;
  }

  .dk-gd__tag {
    font-size: 2rem;
    font-weight: 700;
    line-height: 1;
  }

  .dk-gd__monat {
    font-size: 1.125rem;
  }

  .dk-gd__zeit {
    margin: 0;
    font-size: 1.125rem;
    font-weight: 600;
  }

  .dk-gd__was {
    margin: 0.25rem 0 0;
    font-weight: 600;
  }

  .dk-gd__ort,
  .dk-gd__zusatz,
  .dk-gd__hinweis {
    margin: 0;
    font-size: var(--dk-groesse-klein, 0.875rem);
    color: var(--dk-farbe-gedaempft, color-mix(in srgb, currentColor 70%, transparent));
  }

  .dk-gd__hinweis--fehler {
    color: inherit;
  }

  .dk-gd__link-a {
    color: inherit;
    text-decoration: underline;
    text-underline-offset: 0.15em;
  }

  /* Reihenfolge: der erste __link-Block ist der LINK (Wächter BS-2a2/Dunkel). */

  .dk-gd__link {
    margin: 0.25rem 0 0;
  }

  .dk-gd__link-a:hover {
    text-decoration-thickness: 2px;
  }

  .dk-gd__link-a:focus-visible {
    outline: 2px solid var(--dk-farbe-akzent, currentColor);
    outline-offset: 2px;
  }
</style>
