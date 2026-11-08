<section class="dk-ansprechpartner" lang="de" data-darstellung={darstellung_effektiv}>
  <h2 class="dk-ansprechpartner__titel">{ueberschrift}</h2>
  {#if einleitung}<p class="dk-ansprechpartner__einleitung">{einleitung}</p>{/if}

  {#if ladezustand === 'laedt'}
    <p class="dk-ansprechpartner__hinweis" role="status">{text_laedt}</p>
  {:else if ladezustand === 'fehler'}
    <p class="dk-ansprechpartner__hinweis" role="status">{fehlertext}</p>
  {:else if personen.length === 0}
    <p class="dk-ansprechpartner__hinweis" role="status">{leertext}</p>
  {:else}
    <ul class="dk-ansprechpartner__liste" aria-live="polite">
      {#each personen as person (person.schluessel)}
        <li class="dk-ansprechpartner__eintrag">
          <article class="dk-ansprechpartner__karte">
            {#if person.foto_url}
              <img class="dk-ansprechpartner__bild" src={person.foto_url} alt={person.name} loading="lazy" decoding="async" width="96" height="96" />
            {/if}
            <div class="dk-ansprechpartner__text">
              <h3 class="dk-ansprechpartner__name">{person.name}</h3>
              {#if person.bereich}<p class="dk-ansprechpartner__bereich">{person.bereich}</p>{/if}
              {#if person.kontakt_ziel}
                <p class="dk-ansprechpartner__mehr">
                  <a class="dk-ansprechpartner__knopf" href={person.kontakt_ziel}>{kontakt_text}</a>
                </p>
              {/if}
            </div>
          </article>
        </li>
      {/each}
    </ul>
  {/if}
</section>

<script>
  // Abschnitte sind SERVER-Komponenten: Primo rendert sie mit `svelte/server`
  // (`render(App, …)`); ein Einhaenge-Haken ist dort verboten und der Publish
  // bricht ab. Der Abruf steht deshalb in `$effect` — das laeuft bei SSR nicht
  // und im Browser einmal beim Einhaengen (der Effekt liest keine Abhaengigkeit).

  let {
    ueberschrift = 'Ansprechpartner',
    einleitung = '',
    basisadresse = '',
    bereich = '',
    darstellung = 'karten',
    mit_foto = true,
    kontakt_text = 'Kontakt aufnehmen',
    kontakt_ziel = '/kontakt?postfach={postfach}',
    text_laedt = 'Ansprechpartner werden geladen …',
    leertext = 'Zurzeit sind keine Ansprechpartner veröffentlicht.',
    fehlertext = 'Die Ansprechpartner sind derzeit nicht abrufbar. Bitte später erneut versuchen.'
  } = $props();

  /** @type {'laedt' | 'fertig' | 'fehler'} */
  let ladezustand = $state('laedt');
  /** @type {Array<{schluessel: string, name: string, bereich: string, foto_url: string, kontakt_ziel: string}>} */
  let personen = $state([]);

  const ZEITLIMIT_MS = 8000;

  let darstellung_effektiv = $derived(String(darstellung || '').trim() === 'liste' ? 'liste' : 'karten');
  let fotos_zeigen = $derived(mit_foto !== false && String(mit_foto) !== 'false');

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
   * Bildadresse aus der Lese-API: relativ (`/diakronos/website/bild/person/…`)
   * oder absolut. Relativ bekommt den Ursprung von Diakronos davor.
   */
  function bild_adresse(wert) {
    const text = String(wert || '').trim();
    if (text === '') return '';
    if (/^https?:\/\//i.test(text)) return nur_webadresse(text);
    const basiswert = basis();
    if (basiswert === '' || !text.startsWith('/')) return '';
    return basiswert + text;
  }

  /**
   * Kontakt-Adresse. `{postfach}` wird durch den Slug ersetzt; fehlt ein
   * Postfach, wird der Platzhalter entfernt (der Parameter ist dann leer).
   * Erlaubt sind relative Pfade (`/kontakt`) und absolute http(s)-Adressen —
   * kein `javascript:`-Muster aus einem Feldwert.
   */
  function kontakt_adresse(postfach) {
    const muster = String(kontakt_ziel || '').trim();
    const slug = String(postfach || '').trim();
    if (muster === '' || kontakt_text === '') return '';
    let ziel = muster.replace(/\{postfach\}/g, encodeURIComponent(slug));
    if (slug === '') {
      // Ohne Postfach keinen leeren Parameter hinterlassen.
      ziel = ziel.replace(/[?&]postfach=(?=&|$)/, '').replace(/[?&]$/, '');
    }
    ziel = ziel.trim();
    if (/^https?:\/\//i.test(ziel)) return nur_webadresse(ziel);
    return ziel.startsWith('/') && !ziel.startsWith('//') ? ziel : '';
  }

  // ── Daten holen ─────────────────────────────────────────────────────────
  function abfrageadresse() {
    const basiswert = basis();
    if (basiswert === '') return '';
    const parameter = new URLSearchParams();
    const filter = String(bereich || '').trim();
    if (filter !== '') parameter.set('bereich', filter);
    const anhang = parameter.toString();
    return basiswert + '/website/oeffentlich/ansprechpartner' + (anhang ? '?' + anhang : '');
  }

  /** Antwort der Lese-API -> Anzeigezeilen (Feld-Positivliste der API). */
  function zeilen_aus_antwort(daten) {
    const liste = Array.isArray(daten) ? daten : [];
    const ergebnis = [];
    const gesehen = new Set();
    for (const eintrag of liste) {
      if (!eintrag || typeof eintrag !== 'object') continue;
      const name = String(eintrag.name || '').trim();
      // Ohne Namen gibt es keinen Ansprechpartner (die API liefert solche
      // Zeilen gar nicht — hier trotzdem pruefen, statt „leer" anzuzeigen).
      if (name === '') continue;
      const funktion = String(eintrag.funktion || '').trim();
      let schluessel = funktion !== '' ? funktion : name;
      if (gesehen.has(schluessel)) schluessel = schluessel + '#' + ergebnis.length;
      gesehen.add(schluessel);
      ergebnis.push({
        schluessel,
        name,
        bereich: String(eintrag.bereich || '').trim(),
        foto_url: fotos_zeigen ? bild_adresse(eintrag.foto_url) : '',
        kontakt_ziel: kontakt_adresse(eintrag.postfach)
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
      personen = zeilen_aus_antwort(koerper.message);
      ladezustand = 'fertig';
    } catch (fehler) {
      // Kein Inhalt in die Konsole: der Block zeigt den Fehler selbst an
      // (BS-0 F4 Punkt 3 — component-error kommt im Editor nicht an).
      personen = [];
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
  .dk-ansprechpartner {
    color: var(--dk-farbe-text, inherit);
    background: var(--dk-farbe-flaeche, transparent);
    font-family: var(--dk-schrift, inherit);
    font-size: var(--dk-groesse-text, 1rem);
    box-sizing: border-box;
    padding: var(--dk-abstand, 0.75rem) 0;
    border-top: var(--dk-rahmen-breite, 1px) solid
      var(--dk-farbe-rahmen, color-mix(in srgb, currentColor 25%, transparent));
  }

  .dk-ansprechpartner *,
  .dk-ansprechpartner *::before,
  .dk-ansprechpartner *::after {
    box-sizing: border-box;
  }

  .dk-ansprechpartner__titel {
    margin: 0 0 var(--dk-abstand, 0.75rem);
    font-family: var(--dk-schrift-ueberschrift, var(--dk-schrift, inherit));
    font-size: var(--dk-groesse-ueberschrift, 1.375rem);
    line-height: 1.25;
    color: var(--dk-farbe-ueberschrift, inherit);
  }

  .dk-ansprechpartner__einleitung {
    margin: 0 0 var(--dk-abstand, 0.75rem);
    max-width: 60ch;
  }

  .dk-ansprechpartner__liste {
    margin: 0;
    padding: 0;
    list-style: none;
    display: grid;
    grid-template-columns: 1fr;
    gap: var(--dk-abstand, 0.75rem);
  }

  .dk-ansprechpartner__eintrag {
    min-width: 0;
  }

  .dk-ansprechpartner__karte {
    display: flex;
    flex-direction: column;
    gap: 0.6rem;
    height: 100%;
    padding: var(--dk-abstand, 0.75rem);
    border: var(--dk-rahmen-breite, 1px) solid
      var(--dk-farbe-rahmen, color-mix(in srgb, currentColor 25%, transparent));
    border-radius: var(--dk-rahmen-radius, 0.5rem);
  }

  /* Kein leerer Bildplatz: das <img> wird NUR gerendert, wenn es eine
     Bildadresse gibt — der Textblock beginnt dann direkt mit dem Namen. */
  .dk-ansprechpartner__bild {
    display: block;
    width: 6rem;
    height: 6rem;
    object-fit: cover;
    border-radius: 50%;
  }

  .dk-ansprechpartner__text {
    min-width: 0;
  }

  .dk-ansprechpartner__name {
    margin: 0;
    font-family: var(--dk-schrift-ueberschrift, var(--dk-schrift, inherit));
    font-size: 1.125rem;
    line-height: 1.3;
  }

  .dk-ansprechpartner__bereich {
    margin: 0.15rem 0 0;
    font-size: var(--dk-groesse-klein, 0.875rem);
    color: var(--dk-farbe-gedaempft, color-mix(in srgb, currentColor 70%, transparent));
  }

  .dk-ansprechpartner__mehr {
    margin: 0.6rem 0 0;
    font-size: var(--dk-groesse-klein, 0.875rem);
  }

  .dk-ansprechpartner__knopf {
    /* Akzent nie als Textfarbe (Dunkelmodus): Kontur UND Unterstreichung
       tragen die Auszeichnung, die Schriftfarbe kommt von der Site. */
    display: inline-block;
    color: inherit;
    text-decoration: underline;
    text-underline-offset: 0.15em;
    padding: 0.35rem 0.7rem;
    border: var(--dk-rahmen-breite, 1px) solid var(--dk-farbe-akzent, currentColor);
    border-radius: var(--dk-rahmen-radius, 0.5rem);
  }

  .dk-ansprechpartner__knopf:hover {
    text-decoration-thickness: 2px;
    background: color-mix(in srgb, currentColor 8%, transparent);
  }

  .dk-ansprechpartner__knopf:focus-visible {
    outline: 2px solid var(--dk-farbe-akzent, currentColor);
    outline-offset: 2px;
  }

  .dk-ansprechpartner__hinweis {
    margin: 0;
    color: var(--dk-farbe-gedaempft, color-mix(in srgb, currentColor 70%, transparent));
    font-size: var(--dk-groesse-klein, 0.875rem);
  }

  /* ── Darstellung "liste": Bild neben Text, eine Zeile je Person ───────── */
  .dk-ansprechpartner[data-darstellung='liste'] .dk-ansprechpartner__karte {
    flex-direction: row;
    flex-wrap: wrap;
    align-items: center;
    height: auto;
  }

  .dk-ansprechpartner[data-darstellung='liste'] .dk-ansprechpartner__bild {
    width: 3rem;
    height: 3rem;
    flex: 0 0 auto;
  }

  .dk-ansprechpartner[data-darstellung='liste'] .dk-ansprechpartner__text {
    flex: 1 1 12rem;
  }

  .dk-ansprechpartner[data-darstellung='liste'] .dk-ansprechpartner__mehr {
    margin: 0;
  }

  @media (min-width: 40em) {
    .dk-ansprechpartner[data-darstellung='karten'] .dk-ansprechpartner__liste {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
  }

  @media (min-width: 60em) {
    .dk-ansprechpartner[data-darstellung='karten'] .dk-ansprechpartner__liste {
      grid-template-columns: repeat(3, minmax(0, 1fr));
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .dk-ansprechpartner * {
      transition: none !important;
      animation: none !important;
    }
  }
</style>
