<section class="dk-gruppen" lang="de" data-darstellung={darstellung_effektiv}>
  <h2 class="dk-gruppen__titel">{ueberschrift}</h2>

  {#if ladezustand === "laedt"}
    <p class="dk-gruppen__hinweis" role="status">{text_laedt}</p>
  {:else if ladezustand === "fehler"}
    <p class="dk-gruppen__hinweis" role="status">{fehlertext}</p>
  {:else if gruppen.length === 0}
    <p class="dk-gruppen__hinweis" role="status">{leertext}</p>
  {:else}
    <ul class="dk-gruppen__liste" aria-live="polite">
      {#each gruppen as gruppe (gruppe.schluessel)}
        <li class="dk-gruppen__eintrag">
          <article class="dk-gruppen__karte">
            {#if gruppe.bild_url}
              <img class="dk-gruppen__bild" src={gruppe.bild_url} alt={gruppe.bild_alt} loading="lazy" decoding="async" />
            {/if}
            <h3 class="dk-gruppen__name">{gruppe.name}</h3>
            {#if gruppe.typ}<p class="dk-gruppen__typ">{gruppe.typ}</p>{/if}
            {#if gruppe.beschreibung}<p class="dk-gruppen__text">{gruppe.beschreibung}</p>{/if}
            {#if gruppe.link}
              <p class="dk-gruppen__mehr">
                <a class="dk-gruppen__link" href={gruppe.link} rel="noopener">{text_mehr}</a>
              </p>
            {/if}
          </article>
        </li>
      {/each}
    </ul>
  {/if}
</section>

<script>
  // Abschnitte sind SERVER-Komponenten: Primo rendert sie mit `svelte/server`
  // (`render(App, …)`), dort ist `onMount` verboten und der Publish bricht ab.
  // Der Abruf steht deshalb in `$effect` — das laeuft bei SSR nicht und im
  // Browser einmal beim Einhaengen (der Effekt liest keine Abhaengigkeit).

  let {
    ueberschrift = 'Gruppen',
    basisadresse = '',
    darstellung = 'kacheln',
    gruppentyp = '',
    detail_link = '',
    text_mehr = 'Mehr erfahren',
    text_laedt = 'Gruppen werden geladen …',
    leertext = 'Zurzeit sind keine Gruppen veröffentlicht.',
    fehlertext = 'Die Gruppen sind derzeit nicht abrufbar. Bitte später erneut versuchen.'
  } = $props();

  /** @type {'laedt' | 'fertig' | 'fehler'} */
  let ladezustand = $state('laedt');
  /** @type {Array<{schluessel: string, name: string, typ: string, beschreibung: string, bild_url: string, bild_alt: string, link: string}>} */
  let gruppen = $state([]);

  const ZEITLIMIT_MS = 8000;

  let darstellung_effektiv = $derived(String(darstellung || '').trim() === 'liste' ? 'liste' : 'kacheln');

  // ── Hilfslogik: Adressen ────────────────────────────────────────────────
  // Bewusst in jedem Baustein eigenstaendig (Primo kopiert Bloecke in Sites;
  // ein gemeinsames Modul gaebe es in der Kopie nicht — README, Regel 1).
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

  /** Diakronos-Basisadresse: absolute http(s)-Adresse ohne Schluss-Schraegstrich. */
  function basis() {
    return nur_webadresse(basisadresse);
  }

  /**
   * Detail-Link aus dem Muster. `{slug}` wird ersetzt.
   *
   * Erlaubt sind nur relative Pfade (`/gruppen/kinder`) und absolute
   * http(s)-Adressen — kein `javascript:`-Muster aus einem Feldwert.
   */
  function detail_adresse(slug) {
    const kennung = String(slug || '').trim();
    if (kennung === '') return '';
    const muster = String(detail_link || '').trim();
    if (muster === '') return '';
    let ziel = muster.indexOf('{slug}') >= 0
      ? muster.replace(/\{slug\}/g, encodeURIComponent(kennung))
      : muster.replace(/\/+$/, '') + '/' + encodeURIComponent(kennung);
    ziel = ziel.trim();
    if (/^https?:\/\//i.test(ziel)) return nur_webadresse(ziel);
    // Relativer Pfad: muss mit einem Schraegstrich beginnen (sonst waere es
    // ein relatives Ziel zum Editor-`srcdoc` und damit kaputt).
    return ziel.startsWith('/') && !ziel.startsWith('//') ? ziel : '';
  }

  // ── Bildadresse ─────────────────────────────────────────────────────────
  /**
   * Die Lese-API liefert `bild_url` praefixbewusst, aber moeglicherweise
   * RELATIV (`/diakronos/website/bild/gruppe/x`) — dann kommt der Ursprung
   * von Diakronos davor. Eine absolute Adresse bleibt unveraendert.
   */
  function bild_adresse(wert) {
    const text = String(wert || '').trim();
    if (text === '') return '';
    if (/^https?:\/\//i.test(text)) return nur_webadresse(text);
    const basiswert = basis();
    if (basiswert === '' || !text.startsWith('/')) return '';
    return basiswert + text;
  }

  // ── Daten holen ─────────────────────────────────────────────────────────
  function abfrageadresse() {
    const basiswert = basis();
    if (basiswert === '') return '';
    const parameter = new URLSearchParams();
    const typ = String(gruppentyp || '').trim();
    if (typ !== '') parameter.set('typ', typ);
    const anhang = parameter.toString();
    return basiswert + '/website/oeffentlich/gruppen' + (anhang ? '?' + anhang : '');
  }

  /** Antwort der Lese-API -> Anzeigezeilen (Feld-Positivliste der API). */
  function zeilen_aus_antwort(daten) {
    const liste = Array.isArray(daten) ? daten : [];
    const ergebnis = [];
    const gesehen = new Set();
    for (const eintrag of liste) {
      if (!eintrag || typeof eintrag !== 'object') continue;
      const slug = String(eintrag.slug || '').trim();
      const name = String(eintrag.name || '').trim();
      // Ohne Namen gibt es nichts anzuzeigen.
      if (name === '') continue;
      // Schluessel fuer `#each`: Slug, sonst der Name (mehrfach absichern).
      let schluessel = slug || name;
      if (gesehen.has(schluessel)) schluessel = schluessel + '#' + ergebnis.length;
      gesehen.add(schluessel);
      ergebnis.push({
        schluessel,
        name,
        typ: String(eintrag.typ || '').trim(),
        beschreibung: String(eintrag.beschreibung || '').trim(),
        bild_url: bild_adresse(eintrag.bild_url),
        bild_alt: name,
        link: detail_adresse(slug)
      });
    }
    return ergebnis;
  }

  async function laden() {
    const adresse = abfrageadresse();
    if (adresse === '') {
      // Ohne Adresse gibt es nichts abzurufen: Konfigurationsfehler des
      // Redakteurs, kein Besucherfehler. Gleiche Anzeige wie ein Ladefehler,
      // aber ohne Netzzugriff.
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
      gruppen = zeilen_aus_antwort(koerper.message);
      ladezustand = 'fertig';
    } catch (fehler) {
      // Kein Inhalt in die Konsole: der Block zeigt den Fehler selbst an
      // (BS-0 F4 Punkt 3 — component-error kommt im Editor nicht an).
      gruppen = [];
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
  /* --dk-* NUR LESEN, nie hier deklarieren (BS-0 F5). Vorgaben stehen
     ausschliesslich als Fallback im var()-Aufruf.

     DUNKELMODUS („Weg 1"): der Baustein ERBT von der Site.
       Text        -> inherit                    (Site entscheidet)
       Flaeche     -> transparent
       gedaempft   -> color-mix(... currentColor 70% ...)
       Rahmen      -> color-mix(... currentColor 25% ...)
       Akzent      -> nur Hintergrund/Kontur, nie Textfarbe */
  .dk-gruppen {
    color: var(--dk-farbe-text, inherit);
    background: var(--dk-farbe-flaeche, transparent);
    font-family: var(--dk-schrift, inherit);
    font-size: var(--dk-groesse-text, 1rem);
    box-sizing: border-box;
    padding: var(--dk-abstand, 0.75rem) 0;
    border-top: var(--dk-rahmen-breite, 1px) solid
      var(--dk-farbe-rahmen, color-mix(in srgb, currentColor 25%, transparent));
  }

  .dk-gruppen *,
  .dk-gruppen *::before,
  .dk-gruppen *::after {
    box-sizing: border-box;
  }

  .dk-gruppen__titel {
    margin: 0 0 var(--dk-abstand, 0.75rem);
    font-family: var(--dk-schrift-ueberschrift, var(--dk-schrift, inherit));
    font-size: var(--dk-groesse-ueberschrift, 1.375rem);
    line-height: 1.25;
    color: var(--dk-farbe-ueberschrift, inherit);
  }

  .dk-gruppen__liste {
    margin: 0;
    padding: 0;
    list-style: none;
    display: grid;
    grid-template-columns: 1fr;
    gap: var(--dk-abstand, 0.75rem);
  }

  .dk-gruppen__eintrag {
    min-width: 0;
  }

  .dk-gruppen__karte {
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
    height: 100%;
    padding: var(--dk-abstand, 0.75rem);
    border: var(--dk-rahmen-breite, 1px) solid
      var(--dk-farbe-rahmen, color-mix(in srgb, currentColor 25%, transparent));
    border-radius: var(--dk-rahmen-radius, 0.5rem);
  }

  /* Kein leerer Bildplatz: das <img> wird NUR gerendert, wenn es eine
     Bildadresse gibt — der Textblock beginnt dann direkt mit der
     Ueberschrift. Deshalb hier kein Platzhalter/Rahmen ohne Bild. */
  .dk-gruppen__bild {
    display: block;
    width: 100%;
    height: auto;
    aspect-ratio: 3 / 2;
    object-fit: cover;
    border-radius: var(--dk-rahmen-radius, 0.5rem);
  }

  .dk-gruppen__name {
    margin: 0;
    font-family: var(--dk-schrift-ueberschrift, var(--dk-schrift, inherit));
    font-size: 1.125rem;
    line-height: 1.3;
  }

  .dk-gruppen__typ {
    margin: 0;
    font-size: var(--dk-groesse-klein, 0.875rem);
    color: var(--dk-farbe-gedaempft, color-mix(in srgb, currentColor 70%, transparent));
  }

  .dk-gruppen__text {
    margin: 0;
    white-space: pre-line;
    overflow-wrap: anywhere;
  }

  .dk-gruppen__mehr {
    margin: auto 0 0;
    font-size: var(--dk-groesse-klein, 0.875rem);
  }

  .dk-gruppen__link {
    /* Akzent nie als Textfarbe (Dunkelmodus): Unterstreichung traegt die
       Auszeichnung, die Farbe kommt von der Site. */
    color: inherit;
    text-decoration: underline;
    text-underline-offset: 0.15em;
  }

  .dk-gruppen__link:hover {
    text-decoration-thickness: 2px;
  }

  .dk-gruppen__link:focus-visible {
    outline: 2px solid var(--dk-farbe-akzent, currentColor);
    outline-offset: 2px;
  }

  .dk-gruppen__hinweis {
    margin: 0;
    color: var(--dk-farbe-gedaempft, color-mix(in srgb, currentColor 70%, transparent));
    font-size: var(--dk-groesse-klein, 0.875rem);
  }

  /* ── Darstellung "liste": Bild neben Text, eine Zeile je Gruppe ───────── */
  .dk-gruppen[data-darstellung='liste'] .dk-gruppen__karte {
    flex-direction: row;
    flex-wrap: wrap;
    align-items: flex-start;
    gap: var(--dk-abstand, 0.75rem);
    height: auto;
  }

  .dk-gruppen[data-darstellung='liste'] .dk-gruppen__bild {
    width: 6rem;
    flex: 0 0 auto;
  }

  .dk-gruppen[data-darstellung='liste'] .dk-gruppen__name,
  .dk-gruppen[data-darstellung='liste'] .dk-gruppen__typ,
  .dk-gruppen[data-darstellung='liste'] .dk-gruppen__text,
  .dk-gruppen[data-darstellung='liste'] .dk-gruppen__mehr {
    flex: 1 1 12rem;
    min-width: 0;
  }

  .dk-gruppen[data-darstellung='liste'] .dk-gruppen__mehr {
    flex-basis: 100%;
    margin: 0;
  }

  @media (min-width: 40em) {
    .dk-gruppen[data-darstellung='kacheln'] .dk-gruppen__liste {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
  }

  @media (min-width: 60em) {
    .dk-gruppen[data-darstellung='kacheln'] .dk-gruppen__liste {
      grid-template-columns: repeat(3, minmax(0, 1fr));
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .dk-gruppen * {
      transition: none !important;
      animation: none !important;
    }
  }
</style>
