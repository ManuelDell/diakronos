<section class="dk-neuigkeiten" lang="de" data-darstellung={darstellung_effektiv}>
  <h2 class="dk-neuigkeiten__titel">{ueberschrift}</h2>

  {#if ladezustand === "laedt"}
    <p class="dk-neuigkeiten__hinweis" role="status">{text_laedt}</p>
  {:else if ladezustand === "fehler"}
    <p class="dk-neuigkeiten__hinweis" role="status">{fehlertext}</p>
  {:else if beitraege.length === 0}
    <p class="dk-neuigkeiten__hinweis" role="status">{leertext}</p>
  {:else}
    <ul class="dk-neuigkeiten__liste" aria-live="polite">
      {#each beitraege as beitrag (beitrag.id)}
        <li class="dk-neuigkeiten__eintrag">
          <article class="dk-neuigkeiten__karte">
            {#if beitrag.bild_url}
              <img class="dk-neuigkeiten__bild" src={beitrag.bild_url} alt={beitrag.bild_alt} loading="lazy" decoding="async" />
            {/if}
            <p class="dk-neuigkeiten__kopf">
              {#if beitrag.datum}<time class="dk-neuigkeiten__datum" datetime={beitrag.datum_iso}>{beitrag.datum}</time>{/if}
              {#if beitrag.kategorie}<span class="dk-neuigkeiten__kategorie">{beitrag.kategorie}</span>{/if}
            </p>
            <h3 class="dk-neuigkeiten__name">{beitrag.titel}</h3>
            {#if beitrag.auszug && !offen[beitrag.id]}<p class="dk-neuigkeiten__auszug">{beitrag.auszug}</p>{/if}
            {#if offen[beitrag.id] && beitrag.inhalt_teile.length > 0}
              <div class="dk-neuigkeiten__inhalt" id={beitrag.inhalt_id}>
                {#each beitrag.inhalt_teile as teil, nummer (nummer)}
                  {@html teil.html}
                {/each}
              </div>
            {/if}
            {#if beitrag.aufklappbar && weiterlesen}
              <p class="dk-neuigkeiten__mehr">
                <button
                  type="button"
                  class="dk-neuigkeiten__knopf"
                  aria-expanded={offen[beitrag.id] ? 'true' : 'false'}
                  aria-controls={beitrag.inhalt_id}
                  onclick={() => umschalten(beitrag.id)}
                >{offen[beitrag.id] ? text_zuklappen : text_weiterlesen}</button>
              </p>
            {/if}
          </article>
        </li>
      {/each}
    </ul>
  {/if}
</section>

<script>
  // Abschnitte sind SERVER-Komponenten (Primo rendert mit `svelte/server`,
  // `onMount` ist dort verboten). Abruf in `$effect`, Auf-/Zuklappen ueber
  // `onclick` — beides laeuft nur im Browser.
  //
  // SICHERHEIT (Karte B3): Der Inhalt kommt BEREINIGT aus der API
  // (`website/oeffentlich_inhalt.html_erlaubt`, Allowlist p/br/strong/em/ul/
  // ol/li/a[href http|https|mailto]/h2/h3/blockquote). Trotzdem wird er hier
  // NICHT ungefiltert in `{@html}` gesteckt: `inhalt_teile` entsteht aus einer
  // ZWEITEN Whitelist-Pruefung im Browser (DOM-Parser + Neubau der Knoten).
  // Damit kann auch ein Fehler in der Server-Bereinigung keinen Skript- oder
  // Attribut-Code in die Seite bringen.

  let {
    ueberschrift = 'Neuigkeiten',
    basisadresse = '',
    darstellung = 'karten',
    anzahl = 5,
    kategorie = '',
    bilder_anzeigen = true,
    weiterlesen = true,
    text_weiterlesen = 'Weiterlesen',
    text_zuklappen = 'Zuklappen',
    text_laedt = 'Neuigkeiten werden geladen …',
    leertext = 'Zurzeit sind keine Neuigkeiten veröffentlicht.',
    fehlertext = 'Die Neuigkeiten sind derzeit nicht abrufbar. Bitte später erneut versuchen.'
  } = $props();

  /** @type {'laedt' | 'fertig' | 'fehler'} */
  let ladezustand = $state('laedt');
  /** @type {Array<any>} */
  let beitraege = $state([]);
  /** id -> aufgeklappt? */
  let offen = $state({});

  const ZEITLIMIT_MS = 8000;

  // Erlaubte Elemente der Anzeige — DIESELBE Liste wie der Server
  // (`ERLAUBTE_TAGS` in `website/oeffentlich_inhalt.py`), hier nur als
  // Positivliste fuer den Neubau.
  const ERLAUBTE_TAGS = new Set([
    'P', 'BR', 'STRONG', 'EM', 'UL', 'OL', 'LI', 'A', 'H2', 'H3', 'BLOCKQUOTE'
  ]);
  const ERLAUBTE_SCHEMATA = ['http://', 'https://', 'mailto:'];

  let darstellung_effektiv = $derived(String(darstellung || '').trim() === 'liste' ? 'liste' : 'karten');

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

  /** Praefixbewusste, evtl. relative Bildadresse absolut machen. */
  function bild_adresse(wert) {
    const text = String(wert || '').trim();
    if (text === '') return '';
    if (/^https?:\/\//i.test(text)) return nur_webadresse(text);
    const basiswert = basis();
    if (basiswert === '' || !text.startsWith('/')) return '';
    return basiswert + text;
  }

  function zahl(wert, vorgabe, minimum, maximum) {
    const geprueft = Number(String(wert === null || wert === undefined ? '' : wert).replace(',', '.'));
    if (!Number.isFinite(geprueft)) return vorgabe;
    return Math.min(maximum, Math.max(minimum, Math.trunc(geprueft)));
  }

  // ── Datum in Europe/Berlin ──────────────────────────────────────────────
  const ZEITZONE = 'Europe/Berlin';

  /** "08.11.2026" -> Anzeige; ungueltig -> "". */
  function datumstext(wert) {
    const text = String(wert || '').trim();
    if (text === '') return { anzeige: '', iso: '' };
    const datum = new Date(text.length <= 10 ? text + 'T12:00:00' : text);
    if (Number.isNaN(datum.getTime())) return { anzeige: '', iso: '' };
    const teile = new Intl.DateTimeFormat('de-DE', {
      timeZone: ZEITZONE,
      year: 'numeric',
      month: '2-digit',
      day: '2-digit'
    }).formatToParts(datum);
    const wert_teil = (art) => (teile.find((s) => s.type === art) || {}).value || '';
    const tag = wert_teil('day');
    const monat = wert_teil('month');
    const jahr = wert_teil('year');
    return { anzeige: tag + '.' + monat + '.' + jahr, iso: jahr + '-' + monat + '-' + tag };
  }

  // ── Bereinigtes HTML: ZWEITE Whitelist im Browser ───────────────────────
  /**
   * Baut aus dem bereinigten HTML der API eine Liste sicherer Teil-Bausteine.
   *
   * Vorgehen: `DOMParser` (erzeugt ein INERTES Dokument — Skripte laufen dort
   * nicht, Bilder werden nicht geladen), dann werden die Knoten EINZELN neu
   * aufgebaut: nur erlaubte Elemente, nur `href` an `a`, nur erlaubte
   * Schemata. Ergebnis ist ein Array `{html}` — der Wert stammt aus dem
   * eigenen Neubau und enthaelt ausschliesslich Zeichen, die
   * `escapeHtml`/`escapeAttr` erzeugt haben.
   */
  function sichere_teile(roh) {
    const text = String(roh || '').trim();
    if (text === '') return [];
    if (typeof DOMParser !== 'function') return [];
    let dokument;
    try {
      dokument = new DOMParser().parseFromString('<body>' + text + '</body>', 'text/html');
    } catch (fehler) {
      return [];
    }
    if (!dokument || !dokument.body) return [];
    const ausgabe = [];
    let puffer = '';
    const leeren = () => {
      if (puffer !== '') ausgabe.push({ html: puffer });
      puffer = '';
    };
    for (const knoten of Array.from(dokument.body.childNodes)) {
      if (knoten.nodeType === 3) {
        // Textknoten: nur Text, immer maskiert.
        const wert = String(knoten.nodeValue || '');
        if (wert.trim() !== '') puffer += escapeHtml(wert);
        continue;
      }
      if (knoten.nodeType !== 1) continue;
      const name = String(knoten.nodeName || '').toUpperCase();
      if (!ERLAUBTE_TAGS.has(name)) continue;
      // Block-Elemente trennen die Teile, damit `{@html}` je Block sauber ist.
      if (['P', 'UL', 'OL', 'H2', 'H3', 'BLOCKQUOTE'].includes(name)) leeren();
      puffer += baue_knoten(knoten, name);
    }
    leeren();
    return ausgabe;
  }

  function baue_knoten(knoten, name) {
    if (name === 'BR') return '<br />';
    const innen = Array.from(knoten.childNodes)
      .map((kind) => {
        if (kind.nodeType === 3) return escapeHtml(String(kind.nodeValue || ''));
        if (kind.nodeType !== 1) return '';
        const kind_name = String(kind.nodeName || '').toUpperCase();
        if (!ERLAUBTE_TAGS.has(kind_name)) return '';
        return baue_knoten(kind, kind_name);
      })
      .join('');
    // Die Inhaltselemente tragen eine EIGENE Klasse `dk-fliess`: `{@html}`
    // erzeugt keinen Svelte-Scope-Hash, ein `.dk-neuigkeiten__inhalt p`
    // griffe deshalb nie (und Svelte warnt zurecht "css_unused_selector").
    const klasse = ' class="dk-fliess"';
    if (name === 'A') {
      const ziel = link_ziel(knoten.getAttribute('href'));
      // Zwei Klassen: `dk-fliess` (Fliesstext des Inhalts) und
      // `dk-neuigkeiten__link` (Unterstreichung als farbunabhaengige
      // Auszeichnung, Ae4 — dieselbe Regel wie in den anderen Bausteinen).
      const stueck = '<a class="dk-fliess dk-neuigkeiten__link"'
        + (ziel ? ' href="' + escapeAttr(ziel) + '"' : '')
        + ' rel="noopener noreferrer">';
      return stueck + innen + '</a>';
    }
    const klein = name.toLowerCase();
    return '<' + klein + klasse + '>' + innen + '</' + klein + '>';
  }

  /** Nur http(s)/mailto — Leerraum und Steuerzeichen vorher entfernen. */
  function link_ziel(wert) {
    const ziel = String(wert || '').replace(/[\s\u0000-\u001f\u007f]+/g, '').trim();
    if (ziel === '') return '';
    const klein = ziel.toLowerCase();
    for (const schema of ERLAUBTE_SCHEMATA) {
      if (klein.startsWith(schema)) return ziel;
    }
    return '';
  }

  function escapeHtml(wert) {
    return String(wert)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }

  function escapeAttr(wert) {
    return escapeHtml(wert).replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  function umschalten(id) {
    offen = { ...offen, [id]: !offen[id] };
  }

  // ── Daten holen ─────────────────────────────────────────────────────────
  function abfrageadresse() {
    const basiswert = basis();
    if (basiswert === '') return '';
    const parameter = new URLSearchParams();
    parameter.set('limit', String(zahl(anzahl, 5, 1, 50)));
    const kat = String(kategorie || '').trim();
    if (kat !== '') parameter.set('kategorie', kat);
    return basiswert + '/website/oeffentlich/beitraege?' + parameter.toString();
  }

  /** Antwort der Lese-API -> Anzeigezeilen (Feld-Positivliste der API). */
  function zeilen_aus_antwort(daten) {
    const liste = Array.isArray(daten) ? daten : [];
    const ergebnis = [];
    for (const eintrag of liste) {
      if (!eintrag || typeof eintrag !== 'object') continue;
      const titel = String(eintrag.titel || '').trim();
      const id = String(eintrag.id || '').trim() || titel;
      if (id === '') continue;
      const datum = datumstext(eintrag.datum);
      const inhalt_teile = sichere_teile(eintrag.inhalt);
      ergebnis.push({
        id,
        titel,
        kategorie: String(eintrag.kategorie || '').trim(),
        datum: datum.anzeige,
        datum_iso: datum.iso,
        auszug: String(eintrag.auszug || '').trim(),
        // Ohne Bild kein <img> und kein leerer Platz (Karte B1/B3).
        bild_url: bilder_anzeigen === true ? bild_adresse(eintrag.bild_url) : '',
        bild_alt: titel,
        inhalt_teile,
        inhalt_id: 'dk-neuigkeiten-inhalt-' + id.replace(/[^A-Za-z0-9_-]/g, ''),
        aufklappbar: inhalt_teile.length > 0
      });
    }
    return ergebnis;
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
      if (!koerper || typeof koerper !== 'object' || !('message' in koerper)) {
        throw new Error('Antwortform');
      }
      beitraege = zeilen_aus_antwort(koerper.message);
      ladezustand = 'fertig';
    } catch (fehler) {
      beitraege = [];
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
  /* --dk-* NUR LESEN, nie deklarieren (BS-0 F5). Dunkelmodus: alles erbt
     von der Site (Text inherit, Flaechen transparent, Rahmen per color-mix). */
  .dk-neuigkeiten {
    color: var(--dk-farbe-text, inherit);
    background: var(--dk-farbe-flaeche, transparent);
    font-family: var(--dk-schrift, inherit);
    font-size: var(--dk-groesse-text, 1rem);
    box-sizing: border-box;
    padding: var(--dk-abstand, 0.75rem) 0;
    border-top: var(--dk-rahmen-breite, 1px) solid
      var(--dk-farbe-rahmen, color-mix(in srgb, currentColor 25%, transparent));
  }

  .dk-neuigkeiten *,
  .dk-neuigkeiten *::before,
  .dk-neuigkeiten *::after {
    box-sizing: border-box;
  }

  .dk-neuigkeiten__titel {
    margin: 0 0 var(--dk-abstand, 0.75rem);
    font-family: var(--dk-schrift-ueberschrift, var(--dk-schrift, inherit));
    font-size: var(--dk-groesse-ueberschrift, 1.375rem);
    line-height: 1.25;
    color: var(--dk-farbe-ueberschrift, inherit);
  }

  .dk-neuigkeiten__liste {
    margin: 0;
    padding: 0;
    list-style: none;
    display: grid;
    grid-template-columns: 1fr;
    gap: var(--dk-abstand, 0.75rem);
  }

  .dk-neuigkeiten__eintrag {
    min-width: 0;
  }

  .dk-neuigkeiten__karte {
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
    height: 100%;
    padding: var(--dk-abstand, 0.75rem);
    border: var(--dk-rahmen-breite, 1px) solid
      var(--dk-farbe-rahmen, color-mix(in srgb, currentColor 25%, transparent));
    border-radius: var(--dk-rahmen-radius, 0.5rem);
  }

  .dk-neuigkeiten__bild {
    display: block;
    width: 100%;
    height: auto;
    aspect-ratio: 3 / 2;
    object-fit: cover;
    border-radius: var(--dk-rahmen-radius, 0.5rem);
  }

  .dk-neuigkeiten__kopf {
    margin: 0;
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    align-items: baseline;
    font-size: var(--dk-groesse-klein, 0.875rem);
    color: var(--dk-farbe-gedaempft, color-mix(in srgb, currentColor 70%, transparent));
  }

  .dk-neuigkeiten__kategorie {
    border: var(--dk-rahmen-breite, 1px) solid
      var(--dk-farbe-rahmen, color-mix(in srgb, currentColor 25%, transparent));
    border-radius: var(--dk-rahmen-radius, 0.375rem);
    padding: 0 0.4rem;
  }

  .dk-neuigkeiten__name {
    margin: 0;
    font-family: var(--dk-schrift-ueberschrift, var(--dk-schrift, inherit));
    font-size: 1.125rem;
    line-height: 1.3;
  }

  .dk-neuigkeiten__auszug,
  .dk-neuigkeiten__inhalt {
    margin: 0;
    overflow-wrap: anywhere;
  }

  .dk-neuigkeiten__auszug {
    white-space: pre-line;
  }

  /* Inhalt: die Elemente des bereinigten HTML ruhig setzen (keine
     Farbwerte — Textfarbe kommt von der Site). Sie entstehen aus `{@html}`
     und tragen deshalb KEINEN Svelte-Scope-Hash — Gestaltung ueber
     :global(.dk-fliess), das die Elemente bei der Whitelist-Neubildung
     selbst bekommen. */
  .dk-neuigkeiten :global(.dk-fliess) {
    font: inherit;
  }

  .dk-neuigkeiten :global(p.dk-fliess),
  .dk-neuigkeiten :global(ul.dk-fliess),
  .dk-neuigkeiten :global(ol.dk-fliess),
  .dk-neuigkeiten :global(blockquote.dk-fliess) {
    margin: 0 0 0.5rem;
  }

  .dk-neuigkeiten :global(h2.dk-fliess),
  .dk-neuigkeiten :global(h3.dk-fliess) {
    margin: 0.5rem 0 0.35rem;
    font-family: var(--dk-schrift-ueberschrift, var(--dk-schrift, inherit));
    font-size: 1rem;
    line-height: 1.3;
  }

  .dk-neuigkeiten :global(.dk-neuigkeiten__link) {
    /* Ae4: Unterstreichung traegt die Auszeichnung, nie die Farbe allein. */
    color: inherit;
    text-decoration: underline;
    text-underline-offset: 0.15em;
  }

  .dk-neuigkeiten :global(ul.dk-fliess),
  .dk-neuigkeiten :global(ol.dk-fliess) {
    padding-left: 1.25rem;
  }

  .dk-neuigkeiten :global(blockquote.dk-fliess) {
    border-left: 3px solid var(--dk-farbe-akzent, color-mix(in srgb, currentColor 45%, transparent));
    padding-left: var(--dk-abstand-klein, 0.5rem);
  }

  .dk-neuigkeiten__mehr {
    margin: auto 0 0;
    font-size: var(--dk-groesse-klein, 0.875rem);
  }

  /* Der Knopf ist ein echter <button> (Tastatur, Fokus, aria-expanded) und
     sieht wie ein Link aus — Bausteine laufen ohne DkButton (Primo-Block). */
  .dk-neuigkeiten__knopf {
    appearance: none;
    background: none;
    border: 0;
    padding: 0.25rem 0;
    min-height: 44px;
    font: inherit;
    color: inherit;
    text-decoration: underline;
    text-underline-offset: 0.15em;
    cursor: pointer;
  }

  .dk-neuigkeiten__knopf:hover {
    text-decoration-thickness: 2px;
  }

  .dk-neuigkeiten__knopf:focus-visible {
    outline: 2px solid var(--dk-farbe-akzent, currentColor);
    outline-offset: 2px;
  }

  .dk-neuigkeiten__hinweis {
    margin: 0;
    color: var(--dk-farbe-gedaempft, color-mix(in srgb, currentColor 70%, transparent));
    font-size: var(--dk-groesse-klein, 0.875rem);
  }

  /* ── Darstellung "liste": eine Zeile je Beitrag ───────────────────────── */
  .dk-neuigkeiten[data-darstellung='liste'] .dk-neuigkeiten__karte {
    height: auto;
    padding: var(--dk-abstand-klein, 0.5rem) 0;
    border: 0;
    border-bottom: var(--dk-rahmen-breite, 1px) solid
      var(--dk-farbe-rahmen, color-mix(in srgb, currentColor 25%, transparent));
    border-radius: 0;
  }

  .dk-neuigkeiten[data-darstellung='liste'] .dk-neuigkeiten__eintrag:last-child .dk-neuigkeiten__karte {
    border-bottom: 0;
  }

  .dk-neuigkeiten[data-darstellung='liste'] .dk-neuigkeiten__karte {
    display: grid;
    grid-template-columns: 1fr;
    align-content: start;
  }

  @media (min-width: 40em) {
    .dk-neuigkeiten[data-darstellung='liste'] .dk-neuigkeiten__karte {
      grid-template-columns: 12rem minmax(0, 1fr);
      column-gap: var(--dk-abstand, 0.75rem);
    }

    .dk-neuigkeiten[data-darstellung='liste'] .dk-neuigkeiten__bild {
      grid-row: 1 / span 4;
    }

    .dk-neuigkeiten__karte {
      display: flex;
    }
  }

  @media (min-width: 40em) {
    .dk-neuigkeiten[data-darstellung='karten'] .dk-neuigkeiten__liste {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .dk-neuigkeiten * {
      transition: none !important;
      animation: none !important;
    }
  }
</style>
