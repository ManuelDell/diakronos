<section class="dk-abo" lang="de">
  <h2 class="dk-abo__titel">{ueberschrift}</h2>

  {#if ladezustand === 'laedt'}
    <p class="dk-abo__hinweis" role="status">{text_laedt}</p>
  {:else if ladezustand === 'fehler'}
    <p class="dk-abo__hinweis dk-abo__hinweis--fehler" role="status">{fehlertext}</p>
  {:else if !adressen}
    <p class="dk-abo__hinweis" role="status">{leertext}</p>
  {:else}
    {#if text}<p class="dk-abo__text">{text}</p>{/if}

    <p class="dk-abo__zeile">
      <a class="dk-abo__knopf" href={adressen.webcal}>{text_abo}</a>
    </p>

    <p class="dk-abo__zeile">
      <label class="dk-abo__label" for={feld_id}>{text_https}</label>
      <input class="dk-abo__feld" id={feld_id} type="text" readonly value={adressen.https} />
      <button type="button" class="dk-abo__knopf" onclick={kopieren}>{text_kopieren}</button>
    </p>
    <p class="dk-abo__hinweis" role="status" aria-live="polite">{meldung}</p>

    <h3 class="dk-abo__anleitung-titel">{text_anleitung}</h3>
    <ul class="dk-abo__anleitung">
      <li>{text_handy}</li>
      <li>{text_outlook}</li>
      <li>{text_google}</li>
    </ul>
  {/if}
</section>

<script>
  // BS-2b: wie „Nächste Termine" (BS-2a2) — Primo rendert Abschnitte als
  // SERVER-Komponente; der Abruf gehört in `$effect` (bei SSR aus, im Browser
  // einmal beim Einhängen).

  let {
    id,
    ueberschrift = 'Termine abonnieren',
    basisadresse = '',
    kalender = '',
    text = 'Diesen Kalender können Sie in Ihrem Kalenderprogramm abonnieren. Die Termine werden dann automatisch aktuell gehalten.',
    text_abo = 'Kalender abonnieren',
    text_https = 'Adresse zum Eintragen',
    text_kopieren = 'Adresse kopieren',
    text_kopiert = 'Adresse kopiert',
    text_anleitung = 'So geht es',
    text_handy = 'Am Handy: den Link antippen — das Kalenderprogramm fragt von selbst, ob es den Kalender hinzufügen soll.',
    text_outlook = 'In Outlook: „Kalender“ → „Kalender hinzufügen“ → „Aus dem Internet abonnieren“ und die Adresse einfügen.',
    text_google = 'In Google Kalender: neben „Weitere Kalender“ auf „+“ → „Per URL“ und die Adresse einfügen.',
    text_laedt = 'Abo-Adresse wird geladen …',
    leertext = 'Zurzeit steht kein Kalender zum Abonnieren bereit.',
    fehlertext = 'Die Abo-Adresse ist derzeit nicht abrufbar. Bitte später erneut versuchen.'
  } = $props();

  const ZEITLIMIT_MS = 8000;
  /**
   * Kennung des Adressfeldes (Label-Verknüpfung): aus `$props.id()`, damit SSR
   * und Browser DIESELBE Kennung erzeugen (Review-Befund 08.11.: ein
   * zufaelliger Wert war auf dem Server ein anderer als im Browser — das
   * Label zeigte dann ins Leere).
   */
  const BLOCK_ID = $props.id();
  const FELD_ID = 'dk-abo-adresse-' + String(BLOCK_ID || 'feld');
  // Eine Abfrage je Block — auch dann, wenn Svelte den Effekt erneut anfasst.
  let geladen = false;

  /** @type {'laedt' | 'fertig' | 'fehler'} */
  let ladezustand = $state('laedt');
  /** @type {{webcal: string, https: string} | null} */
  let adressen = $state(null);
  let meldung = $state('');
  let feld_id = FELD_ID;

  // ── Hilfslogik (bewusst im Block: Primo kopiert Blöcke in Sites) ─────────
  function nur_webadresse(wert) {
    const text_wert = String(wert || '').trim();
    if (!/^https?:\/\//i.test(text_wert)) return '';
    const ohne_schraegstrich = text_wert.replace(/\/+$/, '');
    try {
      const geprueft = new URL(ohne_schraegstrich);
      return geprueft.protocol === 'http:' || geprueft.protocol === 'https:' ? ohne_schraegstrich : '';
    } catch (fehler) {
      return '';
    }
  }

  /** Abo-Adressen zu einem Kalender-Slug; ohne Slug "" (nichts anzeigen). */
  function abo_adressen(https_adresse) {
    const https = nur_webadresse(https_adresse);
    if (https === '') return null;
    return { https, webcal: 'webcal://' + https.replace(/^https?:\/\//i, '') };
  }

  // ── Daten holen ─────────────────────────────────────────────────────────
  /**
   * Kalender-Kennung: aus dem Feld. Ist es leer, wird der ERSTE freigegebene
   * Kalender genommen (die Lese-API liefert nur freigegebene) — so
   * funktioniert der Block auch ohne Eintrag, verrät aber nichts Internes.
   */
  function abfrageadresse() {
    const basiswert = nur_webadresse(basisadresse);
    if (basiswert === '') return '';
    return basiswert + '/website/oeffentlich/kalender';
  }

  async function laden() {
    if (geladen) return;
    geladen = true;
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
      const liste = Array.isArray(koerper.message) ? koerper.message : [];
      const gewuenscht = String(kalender || '').trim();
      const treffer = gewuenscht !== ''
        ? liste.find((eintrag) => String((eintrag && eintrag.slug) || '') === gewuenscht)
        : liste[0];
      if (!treffer || !treffer.slug) {
        adressen = null;
        ladezustand = 'fertig';
        return;
      }
      const basiswert = nur_webadresse(basisadresse);
      adressen = abo_adressen(basiswert + '/website/ical/' + encodeURIComponent(String(treffer.slug)) + '.ics');
      ladezustand = adressen === null ? 'fehler' : 'fertig';
    } catch (fehler) {
      adressen = null;
      ladezustand = 'fehler';
    } finally {
      if (wecker !== null) clearTimeout(wecker);
    }
  }

  /** Adresse in die Zwischenablage; ohne Zwischenablage bleibt das Feld markiert. */
  async function kopieren() {
    if (!adressen) return;
    meldung = '';
    try {
      if (navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {
        await navigator.clipboard.writeText(adressen.https);
        meldung = String(text_kopiert || '');
        return;
      }
      throw new Error('keine Zwischenablage');
    } catch (fehler) {
      // Rückfall ohne Rechte: Feld markieren, damit ein Kopieren von Hand geht.
      try {
        const feld = document.getElementById(feld_id);
        if (feld) {
          feld.focus();
          feld.select();
        }
        meldung = String(text_https || '');
      } catch (zweiter) {
        meldung = '';
      }
    }
  }

  $effect(() => {
    laden();
  });
</script>

<style>
  /* --dk-* nur lesen (BS-0 F5); Dunkelmodus: Farben erben (BS-2a „Weg 1"). */
  .dk-abo {
    color: var(--dk-farbe-text, inherit);
    background: var(--dk-farbe-flaeche, transparent);
    font-family: var(--dk-schrift, inherit);
    font-size: var(--dk-groesse-text, 1rem);
    box-sizing: border-box;
    padding: var(--dk-abstand, 0.75rem) 0;
    border-top: var(--dk-rahmen-breite, 1px) solid var(--dk-farbe-rahmen, color-mix(in srgb, currentColor 25%, transparent));
  }

  .dk-abo *,
  .dk-abo *::before,
  .dk-abo *::after {
    box-sizing: border-box;
  }

  .dk-abo__titel {
    margin: 0 0 var(--dk-abstand, 0.75rem);
    font-family: var(--dk-schrift-ueberschrift, var(--dk-schrift, inherit));
    font-size: var(--dk-groesse-ueberschrift, 1.375rem);
    line-height: 1.25;
  }

  .dk-abo__text {
    margin: 0 0 var(--dk-abstand-klein, 0.5rem);
  }

  .dk-abo__zeile {
    margin: 0 0 var(--dk-abstand-klein, 0.5rem);
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
    align-items: center;
  }

  .dk-abo__label {
    flex-basis: 100%;
    font-size: var(--dk-groesse-klein, 0.875rem);
    color: var(--dk-farbe-gedaempft, color-mix(in srgb, currentColor 70%, transparent));
  }

  .dk-abo__feld {
    flex: 1 1 14rem;
    min-width: 0;
    font: inherit;
    font-size: var(--dk-groesse-klein, 0.875rem);
    color: inherit;
    background: var(--dk-farbe-eingabe, transparent);
    border: var(--dk-rahmen-breite, 1px) solid var(--dk-farbe-rahmen, color-mix(in srgb, currentColor 25%, transparent));
    border-radius: var(--dk-rahmen-radius, 0.375rem);
    padding: 0.35rem 0.5rem;
  }

  .dk-abo__knopf {
    font: inherit;
    font-size: var(--dk-groesse-klein, 0.875rem);
    color: inherit;
    background: transparent;
    border: var(--dk-rahmen-breite, 1px) solid var(--dk-farbe-akzent, currentColor);
    border-radius: var(--dk-rahmen-radius, 0.375rem);
    padding: 0.35rem 0.7rem;
    text-decoration: none;
    cursor: pointer;
    display: inline-block;
  }

  .dk-abo__knopf:hover {
    text-decoration: underline;
  }

  /* Link-Auszeichnung: NICHT nur Farbe (Ä4, BS-2a2) — die Unterstreichung
     trägt sie. Der Abo-Link ist ein Knopf (`__knopf`), deshalb steht die
     Regel hier an dessen Stelle; sie wird beim Hover wiederholt, weil
     manche Site-Stile Links global ent-unterstreichen. */
  a.dk-abo__knopf {
    text-decoration: underline;
    text-underline-offset: 0.15em;
  }

  /* Für den Wächter ohne Elementteil (BS-2a2 prüft den __link-Block jedes
     Bausteins, der ein <a> rendert) und als Zusicherung, wenn ein Site-Stil
     die Unterstreichung global abschaltet. */
  .dk-abo__link {
    color: inherit;
    text-decoration: underline;
    text-underline-offset: 0.15em;
  }

  .dk-abo__knopf:focus-visible,
  .dk-abo__feld:focus-visible {
    outline: 2px solid var(--dk-farbe-akzent, currentColor);
    outline-offset: 2px;
  }

  .dk-abo__anleitung-titel {
    margin: var(--dk-abstand, 0.75rem) 0 0.25rem;
    font-size: 1rem;
  }

  .dk-abo__anleitung {
    margin: 0;
    padding-left: 1.2rem;
    font-size: var(--dk-groesse-klein, 0.875rem);
    color: var(--dk-farbe-gedaempft, color-mix(in srgb, currentColor 70%, transparent));
  }

  .dk-abo__anleitung li {
    margin-bottom: 0.2rem;
  }

  .dk-abo__hinweis {
    margin: 0;
    font-size: var(--dk-groesse-klein, 0.875rem);
    color: var(--dk-farbe-gedaempft, color-mix(in srgb, currentColor 70%, transparent));
  }

  .dk-abo__hinweis--fehler {
    color: inherit;
  }
</style>
