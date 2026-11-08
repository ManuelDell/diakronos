<section class="dk-anmeldung" lang="de">
  <h2 class="dk-anmeldung__titel">{ueberschrift}</h2>

  {#if ladezustand === "laedt"}
    <p class="dk-anmeldung__hinweis" role="status">{text_laedt}</p>
  {:else if ladezustand === "fehler"}
    <p class="dk-anmeldung__hinweis" role="status">{fehlertext}</p>
  {:else if zeilen.length === 0}
    <p class="dk-anmeldung__hinweis" role="status">{leertext}</p>
  {:else}
    <ul class="dk-anmeldung__liste" aria-live="polite">
      {#each zeilen as termin (termin.id)}
        <li class="dk-anmeldung__eintrag">
          <div class="dk-anmeldung__text">
            <p class="dk-anmeldung__wann">
              <span class="dk-anmeldung__tag">{termin.tag}</span>
              {#if termin.uhrzeit}<span class="dk-anmeldung__uhr">{termin.uhrzeit}</span>{/if}
            </p>
            <p class="dk-anmeldung__was">
              <span class="dk-anmeldung__name">{termin.titel}</span>
              {#if termin.ort}<span class="dk-anmeldung__wo">{termin.ort}</span>{/if}
            </p>
          </div>
          {#if termin.anmeldung_url}
            <p class="dk-anmeldung__knopfzeile">
              {#if neuer_tab}
                <a class="dk-anmeldung__knopf dk-anmeldung__link" href={termin.anmeldung_url} rel="noopener noreferrer" target="_blank">{knopftext}</a>
              {:else}
                <a class="dk-anmeldung__knopf dk-anmeldung__link" href={termin.anmeldung_url} rel="noopener noreferrer">{knopftext}</a>
              {/if}
            </p>
          {/if}
        </li>
      {/each}
    </ul>
  {/if}
</section>

<script>
  // Abschnitte sind SERVER-Komponenten (Primo rendert mit `svelte/server`,
  // `onMount` ist dort verboten). Abruf in `$effect`.
  //
  // Die Anmeldung ist die BESTEHENDE Diakronos-Gast-Anmeldung: die Adresse
  // kommt fertig aus der Lese-API (`anmeldung_url`, gebaut von
  // `anmeldung.registrierungslink.link_anzeige` — praefixbewusst, nur bei
  // aktivem Gast-Link im Gueltigkeitsfenster). Der Baustein baut KEINE
  // eigene Anmeldung und erfindet keine Adresse.

  let {
    ueberschrift = 'Anmeldung',
    basisadresse = '',
    kalender = '',
    kennung = '',
    anzahl = 10,
    neuer_tab = false,
    knopftext = 'Jetzt anmelden',
    text_laedt = 'Termine werden geladen …',
    leertext = 'Zurzeit ist keine Anmeldung möglich.',
    fehlertext = 'Die Termine sind derzeit nicht abrufbar. Bitte später erneut versuchen.'
  } = $props();

  /** @type {'laedt' | 'fertig' | 'fehler'} */
  let ladezustand = $state('laedt');
  /** @type {Array<{id: string, tag: string, uhrzeit: string, titel: string, ort: string, anmeldung_url: string}>} */
  let zeilen = $state([]);

  const ZEITLIMIT_MS = 8000;
  const ZEITZONE = 'Europe/Berlin';

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

  /** Diakronos-Basisadresse: absolute http(s)-Adresse ohne Schluss-Schraegstrich. */
  function basis() {
    return nur_webadresse(basisadresse);
  }

  /**
   * Anmeldeadresse des Termins.
   *
   * Die API liefert sie RELATIV, wenn in Diakronos keine oeffentliche Adresse
   * gepflegt ist (`/diakonos/gast?token=…`) — dann kommt der Ursprung von
   * Diakronos davor. Eine absolute http(s)-Adresse bleibt unveraendert; alles
   * andere (z. B. `javascript:`) faellt auf `""` und der Knopf entfaellt.
   */
  function anmelde_adresse(wert) {
    const text = String(wert || '').trim();
    if (text === '') return '';
    if (/^https?:\/\//i.test(text)) return nur_webadresse(text);
    const basiswert = basis();
    if (basiswert === '' || !text.startsWith('/')) return '';
    // ABNAHMEBEFUND 07.11.: die Lese-API liefert den Pfad MIT Praefix
    // (`/diakronos/diakonos/gast?token=…`, aus `link_anzeige`), die
    // Diakronos-Adresse im Feld traegt ihn aber auch schon
    // (`https://gemeinde.example/diakronos`). Einfaches Anhaengen ergaebe
    // `/diakronos/diakronos/…` — ein toter Link. Deshalb: traegt die
    // Basisadresse denselben Pfadanfang wie das Ziel, wird er nur EINMAL
    // gesetzt.
    try {
      const ziel = new URL(text, basiswert + '/');
      const basis_teile = new URL(basiswert);
      // Pfad der Basis (z. B. "/diakronos") — leer, wenn die Adresse ohne
      // Praefix laeuft.
      const basis_pfad = basis_teile.pathname.replace(/\/+$/, '');
      if (basis_pfad !== '' && ziel.pathname.startsWith(basis_pfad + '/')) {
        // Der Pfad traegt den Praefix bereits: Zielpfad OHNE ihn anhaengen.
        const rest = ziel.pathname.slice(basis_pfad.length);
        return basiswert + rest + ziel.search;
      }
      return basis_teile.origin + ziel.pathname + ziel.search;
    } catch (fehler) {
      return '';
    }
  }

  /** Kennungen aus einem Textfeld: "a, b" oder "a" (leer -> leere Liste). */
  function kennungen(wert) {
    return String(wert || '')
      .split(',')
      .map((teil) => teil.trim())
      .filter((teil) => teil !== '');
  }

  // ── Hilfslogik: Datum/Uhrzeit in Europe/Berlin ──────────────────────────
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
  /**
   * Die Lese-API (L2) filtert seit BS-2c2 SELBST auf „nur mit Anmeldung“:
   * ``nur_anmeldung=1`` liefert ausschliesslich Termine mit fertiger
   * ``anmeldung_url``, und ``limit`` gilt fuer DIESE Liste (nicht fuer eine
   * Vorauswahl). Vorher holte der Baustein das ganze Zeitfenster mit
   * ``limit=500`` und filterte im Browser — bei vielen Terminen ohne
   * Anmeldung kam dadurch weniger an, als „Anzahl“ versprach.
   *
   * ``kennung``: ist eine Gruppe gemeint, wird serverseitig ueber ``gruppe``
   * gefiltert; ein einzelner Termin laesst sich ueber die oeffentliche
   * Kennung NICHT adressieren (die Lese-API hat dafuer keinen Endpunkt) — dann
   * bleibt die Pruefung auf `id` als zweite Stufe im Ergebnis (der Filter
   * ``nur_anmeldung`` und die Feld-Positivliste der API gelten weiter).
   */
  function abfrageadresse() {
    const basiswert = basis();
    if (basiswert === '') return '';
    const heute = new Date();
    const bis = new Date(heute.getTime() + 400 * 24 * 60 * 60 * 1000);
    const parameter = new URLSearchParams();
    parameter.set('von', isodatum(heute));
    parameter.set('bis', isodatum(bis));
    parameter.set('nur_anmeldung', '1');
    // Etwas Luft ueber „Anzahl“: eine Kennung/ein Einzeltermin wird erst im
    // Ergebnis geprueft, und die API deckelt ohnehin bei 500.
    parameter.set('limit', String(Math.min(500, zahl(anzahl, 10, 1, 50) * 5)));
    const kalenderliste = kennungen(kalender);
    if (kalenderliste.length > 0) parameter.set('kalender', kalenderliste.join(','));
    const kennungswert = String(kennung || '').trim();
    // Gruppen-Kennung geht an den Server; alles andere wird unten auf `id` geprueft.
    if (kennungswert !== '' && !/^[a-f0-9]{32}$/i.test(kennungswert)) {
      parameter.set('gruppe', kennungswert);
    }
    return basiswert + '/website/oeffentlich/termine?' + parameter.toString();
  }

  /** Antwort der Lese-API -> Anzeigezeilen (nur Termine mit Anmeldung). */
  function zeilen_aus_antwort(daten) {
    const liste = Array.isArray(daten) ? daten : [];
    const gewuenschte_kennung = String(kennung || '').trim();
    const hoechstzahl = zahl(anzahl, 10, 1, 50);
    const ergebnis = [];
    for (const eintrag of liste) {
      if (!eintrag || typeof eintrag !== 'object') continue;
      const adresse = anmelde_adresse(eintrag.anmeldung_url);
      // Ohne brauchbare Anmeldeadresse gehoert der Termin nicht hierher.
      if (adresse === '') continue;
      const id = String(eintrag.id || '').trim();
      if (gewuenschte_kennung !== '' && id !== gewuenschte_kennung
          && String(eintrag.gruppe?.slug || '').trim() !== gewuenschte_kennung) {
        continue;
      }
      const beginn = als_datum(eintrag.beginn);
      if (beginn === null) continue;
      const zeit = eintrag.ganztaegig === true ? '' : zeitfenster(eintrag.beginn, eintrag.ende);
      const zeitraum = ende_text(beginn, eintrag.ende);
      ergebnis.push({
        id: id || tagestext(beginn) + String(eintrag.titel || ''),
        tag: tagestext(beginn) + (zeitraum !== '' ? ' – ' + zeitraum : ''),
        uhrzeit: zeit,
        titel: String(eintrag.titel || '').trim(),
        ort: String(eintrag.ort || '').trim(),
        anmeldung_url: adresse
      });
      if (ergebnis.length >= hoechstzahl) break;
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
      zeilen = zeilen_aus_antwort(koerper.message);
      ladezustand = 'fertig';
    } catch (fehler) {
      zeilen = [];
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
  .dk-anmeldung {
    color: var(--dk-farbe-text, inherit);
    background: var(--dk-farbe-flaeche, transparent);
    font-family: var(--dk-schrift, inherit);
    font-size: var(--dk-groesse-text, 1rem);
    box-sizing: border-box;
    padding: var(--dk-abstand, 0.75rem) 0;
    border-top: var(--dk-rahmen-breite, 1px) solid
      var(--dk-farbe-rahmen, color-mix(in srgb, currentColor 25%, transparent));
  }

  .dk-anmeldung *,
  .dk-anmeldung *::before,
  .dk-anmeldung *::after {
    box-sizing: border-box;
  }

  .dk-anmeldung__titel {
    margin: 0 0 var(--dk-abstand, 0.75rem);
    font-family: var(--dk-schrift-ueberschrift, var(--dk-schrift, inherit));
    font-size: var(--dk-groesse-ueberschrift, 1.375rem);
    line-height: 1.25;
    color: var(--dk-farbe-ueberschrift, inherit);
  }

  .dk-anmeldung__liste {
    margin: 0;
    padding: 0;
    list-style: none;
  }

  .dk-anmeldung__eintrag {
    display: flex;
    flex-direction: column;
    gap: var(--dk-abstand-klein, 0.5rem);
    padding: var(--dk-abstand-klein, 0.5rem) 0;
    border-bottom: var(--dk-rahmen-breite, 1px) solid
      var(--dk-farbe-rahmen, color-mix(in srgb, currentColor 25%, transparent));
  }

  .dk-anmeldung__eintrag:last-child {
    border-bottom: 0;
  }

  .dk-anmeldung__text {
    min-width: 0;
  }

  .dk-anmeldung__wann {
    margin: 0;
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    font-size: var(--dk-groesse-klein, 0.875rem);
    color: var(--dk-farbe-gedaempft, color-mix(in srgb, currentColor 70%, transparent));
  }

  .dk-anmeldung__tag,
  .dk-anmeldung__name {
    font-weight: 600;
  }

  .dk-anmeldung__was {
    margin: 0;
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    align-items: baseline;
  }

  .dk-anmeldung__wo {
    font-size: var(--dk-groesse-klein, 0.875rem);
    color: var(--dk-farbe-gedaempft, color-mix(in srgb, currentColor 70%, transparent));
  }

  .dk-anmeldung__knopfzeile {
    margin: 0;
  }

  /* Ein <a>, der wie ein Knopf aussieht: Ziel ist ein Link zur bestehenden
     Gast-Anmeldung, also semantisch ein Link (kein <button>). Mindestens
     44 px hoch (Touch-Ziel K4); Farbe nur ueber --dk-*, Akzent als Flaeche
     bzw. Kontur — nie als Textfarbe (Dunkelmodus). Die Unterstreichung der
     Link-Klasse traegt die Auszeichnung unabhaengig von der Farbe (Ae4). */
  .dk-anmeldung__knopf {
    display: inline-block;
    min-height: 44px;
    padding: 0.6rem 1rem;
    font: inherit;
    font-weight: 600;
    color: var(--dk-farbe-knopf-text, inherit);
    background: var(--dk-farbe-akzent, transparent);
    border: var(--dk-rahmen-breite, 1px) solid
      var(--dk-farbe-akzent, color-mix(in srgb, currentColor 45%, transparent));
    border-radius: var(--dk-rahmen-radius, 0.375rem);
    text-decoration: none;
    text-align: center;
    line-height: 1.4;
  }

  .dk-anmeldung__link {
    /* Ae4: Unterstreichung traegt die Auszeichnung, nicht die Farbe. */
    text-decoration: underline;
    text-underline-offset: 0.15em;
  }

  .dk-anmeldung__knopf:hover {
    text-decoration-thickness: 2px;
  }

  .dk-anmeldung__knopf:focus-visible {
    outline: 2px solid var(--dk-farbe-akzent, currentColor);
    outline-offset: 2px;
  }

  .dk-anmeldung__hinweis {
    margin: 0;
    color: var(--dk-farbe-gedaempft, color-mix(in srgb, currentColor 70%, transparent));
    font-size: var(--dk-groesse-klein, 0.875rem);
  }

  @media (min-width: 40em) {
    .dk-anmeldung__eintrag {
      flex-direction: row;
      align-items: center;
      justify-content: space-between;
      gap: var(--dk-abstand, 0.75rem);
    }

    .dk-anmeldung__knopfzeile {
      flex: 0 0 auto;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .dk-anmeldung * {
      transition: none !important;
      animation: none !important;
    }
  }
</style>
