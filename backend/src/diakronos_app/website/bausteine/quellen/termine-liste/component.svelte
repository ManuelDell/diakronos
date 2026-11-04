<section class="dk-termine" lang="de" data-darstellung={darstellung_effektiv}>
  <h2 class="dk-termine__titel">{ueberschrift}</h2>

  {#if ladezustand === "laedt"}
    <p class="dk-termine__hinweis" role="status">{text_laedt}</p>
  {:else if ladezustand === "fehler"}
    <p class="dk-termine__hinweis dk-termine__hinweis--fehler" role="status">{fehlertext}</p>
  {:else if zeilen.length === 0}
    <p class="dk-termine__hinweis" role="status">{leertext}</p>
  {:else}
    <ul class="dk-termine__liste" aria-live="polite">
      {#each zeilen as termin (termin.id)}
        <li class="dk-termine__eintrag">
          <p class="dk-termine__wann">
            <span class="dk-termine__tag">{termin.tag}</span>
            {#if termin.zeitraum}<span class="dk-termine__bis">– {termin.zeitraum}</span>{/if}
            {#if termin.uhrzeit}<span class="dk-termine__uhr">{termin.uhrzeit}</span>{/if}
          </p>
          <p class="dk-termine__was">
            <span class="dk-termine__name">{termin.titel}</span>
            {#if termin.kategorie}<span class="dk-termine__kategorie">{termin.kategorie}</span>{/if}
          </p>
          {#if ort_anzeigen && termin.ort}<p class="dk-termine__wo">{termin.ort}</p>{/if}
          {#if termin.anmeldung_url}
            <p class="dk-termine__anmeldung">
              <a class="dk-termine__link" href={termin.anmeldung_url} rel="noopener">{text_anmeldung}</a>
            </p>
          {/if}
        </li>
      {/each}
    </ul>
  {/if}

  {#if mehr_adresse}
    <p class="dk-termine__mehr">
      <a class="dk-termine__link" href={mehr_adresse}>{mehr_text}</a>
    </p>
  {/if}
</section>

<script>
  // BS-2a2 (Abnahme-Befund): Primo rendert Abschnitte mit `svelte/server`
  // (`render(App, …)`) — dort ist `onMount` verboten („lifecycle_outside_component"),
  // der Publish bricht ab. Abschnitte sind SERVER-Komponenten: der Abruf gehoert
  // deshalb in `$effect` — das laeuft bei SSR NICHT und im Browser genau einmal
  // beim Einhaengen (der Effekt liest keine Abhaengigkeit, Wiederholungen gibt es
  // daher nicht). Der Lebenszyklus-Import entfaellt ganz: toter Code.

  let {
    ueberschrift = 'Nächste Termine',
    basisadresse = '',
    darstellung = 'liste',
    anzahl = 5,
    zeitraum = 90,
    kalender = '',
    kategorie = '',
    gruppe = '',
    ort_anzeigen = true,
    mehr_link = '',
    mehr_text = 'Alle Termine',
    text_ganztaegig = 'ganztägig',
    text_laedt = 'Termine werden geladen …',
    text_anmeldung = 'Zur Anmeldung',
    leertext = 'Zurzeit sind keine Termine angekündigt.',
    fehlertext = 'Die Termine sind derzeit nicht abrufbar. Bitte später erneut versuchen.'
  } = $props();

  /** @type {'laedt' | 'fertig' | 'fehler'} */
  let ladezustand = $state('laedt');
  /** @type {Array<{id: string, tag: string, zeitraum: string, uhrzeit: string, titel: string, ort: string, kategorie: string, anmeldung_url: string}>} */
  let zeilen = $state([]);

  const ZEITLIMIT_MS = 8000;
  const STELLEN = { liste: 'folge', kompakt: 'kompakt', karten: 'karten' };

  let darstellung_effektiv = $derived(STELLEN[String(darstellung || '').trim()] || 'folge');
  let mehr_adresse = $derived(nur_webadresse(mehr_link));

  // ── Hilfslogik: Adressen ────────────────────────────────────────────────
  // Bewusst in jedem Baustein eigenstaendig (Primo kopiert Bloecke in Sites;
  // ein gemeinsames Modul gaebe es in der Kopie nicht — siehe README, Regel 1).
  function nur_webadresse(wert) {
    const text = String(wert || '').trim();
    if (!/^https?:\/\//i.test(text)) return '';
    const ohne_schraegstrich = text.replace(/\/+$/, '');
    try {
      // Pruefen, ob die Adresse ueberhaupt parst (und ob sie Tab/Zeilenumbruch enthaelt).
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

  /** Kennungen aus einem Textfeld: "a, b" oder "a" (leer -> leere Liste). */
  function kennungen(wert) {
    return String(wert || '')
      .split(',')
      .map((teil) => teil.trim())
      .filter((teil) => teil !== '');
  }

  // ── Hilfslogik: Datum/Uhrzeit in Europe/Berlin ──────────────────────────
  const ZEITZONE = 'Europe/Berlin';
  const WOCHENTAGE = ['So', 'Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa'];

  /** ISO-Zeitpunkt -> Date; ungueltig -> null. */
  function als_datum(wert) {
    const text = String(wert || '').trim();
    if (text === '') return null;
    const datum = new Date(text);
    return Number.isNaN(datum.getTime()) ? null : datum;
  }

  /** Teile eines Zeitpunkts in der Zeitzone der Gemeinde (de-DE). */
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

  /** "Sa., 08.11." — Wochentagskuerzel in der Zeitzone der Gemeinde. */
  function tagestext(datum) {
    const wochentag = new Intl.DateTimeFormat('de-DE', {
      timeZone: ZEITZONE,
      weekday: 'short'
    }).format(datum);
    const { tag, monat } = teile(datum);
    return wochentag.replace(/\.$/, '') + '., ' + tag + '.' + monat + '.';
  }

  /**
   * Ende eines mehrtägigen Termins: "So., 09.11." — sonst "".
   *
   * F1: Ein mehrtägiger/ganztägiger Termin braucht seinen Zeitraum, sonst
   * liest er sich wie ein eintägiger. Das Ende kommt UNVERÄNDERT aus der
   * Antwort: Diakronos speichert das Ganztags-Ende EINSCHLIESSLICH und die
   * Lese-API gibt es so aus (`ende` = letzter Tag) — es wird KEIN Tag
   * abgezogen. Liegt das Ende am selben Kalendertag wie der Beginn
   * (eintägig, oder ein Termin bis 23:59 desselben Tages), bleibt das Feld
   * leer.
   */
  function ende_text(beginn, ende) {
    const ende_datum = als_datum(ende);
    if (ende_datum === null) return '';
    if (isodatum(beginn) === isodatum(ende_datum)) return '';
    return tagestext(ende_datum);
  }

  /** "10:00" in der Zeitzone der Gemeinde (24-Stunden-Form). */
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

  /** ISO-JJJJ-MM-TT in der Zeitzone der Gemeinde (fuer den Zeitfenster-Parameter). */
  function isodatum(datum) {
    const { tag, monat, jahr } = teile(datum);
    return jahr + '-' + monat + '-' + tag;
  }

  /** "10:00 – 11:30" aus Beginn/Ende; ohne Ende nur der Beginn. */
  function zeitfenster(beginn, ende) {
    const start = als_datum(beginn);
    if (start === null) return '';
    const ende_datum = als_datum(ende);
    if (ende_datum === null) return uhrzeittext(start);
    if (isodatum(start) !== isodatum(ende_datum)) return uhrzeittext(start);
    return uhrzeittext(start) + ' – ' + uhrzeittext(ende_datum);
  }

  /** Zahl aus einem Feldwert; unbrauchbar -> Vorgabe. */
  function zahl(wert, vorgabe, minimum, maximum) {
    const geprueft = Number(String(wert === null || wert === undefined ? '' : wert).replace(',', '.'));
    if (!Number.isFinite(geprueft)) return vorgabe;
    return Math.min(maximum, Math.max(minimum, Math.trunc(geprueft)));
  }

  // ── Daten holen ─────────────────────────────────────────────────────────
  function abfrageadresse() {
    const basiswert = basis();
    if (basiswert === '') return '';
    const heute = new Date();
    const bis = new Date(heute.getTime() + zahl(zeitraum, 90, 1, 400) * 24 * 60 * 60 * 1000);
    const parameter = new URLSearchParams();
    parameter.set('von', isodatum(heute));
    parameter.set('bis', isodatum(bis));
    parameter.set('limit', String(zahl(anzahl, 5, 1, 50)));
    const kalenderliste = kennungen(kalender);
    if (kalenderliste.length > 0) parameter.set('kalender', kalenderliste.join(','));
    const kategorie_wert = String(kategorie || '').trim();
    if (kategorie_wert !== '') parameter.set('kategorie', kategorie_wert);
    const gruppe_wert = String(gruppe || '').trim();
    if (gruppe_wert !== '') parameter.set('gruppe', gruppe_wert);
    return basiswert + '/website/oeffentlich/termine?' + parameter.toString();
  }

  /** Antwort der Lese-API -> Anzeigezeilen (Feld-Positivliste der API). */
  function zeilen_aus_antwort(daten) {
    const liste = Array.isArray(daten) ? daten : [];
    const ergebnis = [];
    for (const eintrag of liste) {
      if (!eintrag || typeof eintrag !== 'object') continue;
      const beginn = als_datum(eintrag.beginn);
      if (beginn === null) continue;
      // Ganztaegig: keine Uhrzeit anzeigen (statt "00:00") — sonst liest es
      // sich wie ein Termin um Mitternacht. Der Zeitraum (F1) gilt fuer ALLE
      // mehrtägigen Termine, ganztägig wie mit Uhrzeit.
      const zeit = eintrag.ganztaegig === true ? '' : zeitfenster(eintrag.beginn, eintrag.ende);
      ergebnis.push({
        id: String(eintrag.id || '') || tagestext(beginn) + String(eintrag.titel || ''),
        tag: tagestext(beginn),
        zeitraum: ende_text(beginn, eintrag.ende),
        uhrzeit: zeit === '' && eintrag.ganztaegig === true ? text_ganztaegig : zeit,
        titel: String(eintrag.titel || '').trim(),
        ort: String(eintrag.ort || '').trim(),
        kategorie: String(eintrag.kategorie || '').trim(),
        anmeldung_url: nur_webadresse(eintrag.anmeldung_url)
      });
    }
    return ergebnis;
  }

  async function laden() {
    const adresse = abfrageadresse();
    if (adresse === '') {
      // Ohne Adresse gibt es nichts abzurufen: das ist ein Konfigurations-
      // fehler des Redakteurs, kein Besucherfehler. Gleiche Anzeige wie ein
      // Ladefehler — aber ohne Netzzugriff.
      ladezustand = 'fehler';
      return;
    }
    // Zeitlimit: ein haengender Diakronos-Server darf den Block nicht
    // dauerhaft im Ladezustand lassen (kein axios, kein Polyfill).
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
      // Kein Inhalt in die Konsole: der Block zeigt den Fehler selbst an
      // (BS-0 F4 Punkt 3 — component-error kommt im Editor nicht an).
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
  /* --dk-* NUR LESEN, nie hier deklarieren (BS-0 F5). Die Vorgaben stehen
     ausschliesslich als Fallback im var()-Aufruf.

     DUNKELMODUS (Entscheidung Orchestrator 2026-11-04, „Weg 1"): der Baustein
     ERBT von der Site statt eigene Farben zu erzwingen. Ein fester heller
     Text-Fallback (frueher: dunkles Grau) war auf dunklen Primo-Sites
     unlesbar (Kontrast ~1,3:1). Deshalb:
       Text        -> inherit            (Site entscheidet)
       Fläche      -> transparent
       gedämpft    -> color-mix(in srgb, currentColor 70%, transparent)
       Rahmen      -> color-mix(in srgb, currentColor 25%, transparent)
       Akzent      -> NUR Hintergrund/Kontur/Rahmen, nie Textfarbe
       Links/Warn  -> inherit + Unterstreichung bzw. Warn-Rahmen
     color-mix() folgt der geerbten Textfarbe, also in beiden Modi korrekt. */
  .dk-termine {
    color: var(--dk-farbe-text, inherit);
    background: var(--dk-farbe-flaeche, transparent);
    font-family: var(--dk-schrift, inherit);
    font-size: var(--dk-groesse-text, 1rem);
    box-sizing: border-box;
    padding: var(--dk-abstand, 0.75rem) 0;
    border-top: var(--dk-rahmen-breite, 1px) solid
      var(--dk-farbe-rahmen, color-mix(in srgb, currentColor 25%, transparent));
  }

  .dk-termine *,
  .dk-termine *::before,
  .dk-termine *::after {
    box-sizing: border-box;
  }

  .dk-termine__titel {
    margin: 0 0 var(--dk-abstand, 0.75rem);
    font-family: var(--dk-schrift-ueberschrift, var(--dk-schrift, inherit));
    font-size: var(--dk-groesse-ueberschrift, 1.375rem);
    line-height: 1.25;
    color: var(--dk-farbe-ueberschrift, inherit);
  }

  .dk-termine__liste {
    margin: 0;
    padding: 0;
    list-style: none;
  }

  .dk-termine__eintrag {
    display: flex;
    flex-direction: column;
    gap: 0.15rem;
    padding: var(--dk-abstand-klein, 0.5rem) 0;
    border-bottom: var(--dk-rahmen-breite, 1px) solid var(--dk-farbe-rahmen, color-mix(in srgb, currentColor 25%, transparent));
  }

  .dk-termine__eintrag:last-child {
    border-bottom: 0;
  }

  .dk-termine__wann {
    margin: 0;
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    font-size: var(--dk-groesse-klein, 0.875rem);
    color: var(--dk-farbe-gedaempft, color-mix(in srgb, currentColor 70%, transparent));
  }

  .dk-termine__tag {
    font-weight: 600;
  }

  /* F1: Ende eines mehrtägigen Termins — gleiche Zeile wie Beginn, etwas
     leiser, damit „Fr., 07.11. – So., 09.11." als EIN Zeitraum liest. */
  .dk-termine__bis {
    white-space: nowrap;
  }

  .dk-termine__was {
    margin: 0;
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    align-items: baseline;
  }

  .dk-termine__name {
    font-weight: 600;
  }

  .dk-termine__kategorie {
    font-size: var(--dk-groesse-klein, 0.875rem);
    color: var(--dk-farbe-gedaempft, color-mix(in srgb, currentColor 70%, transparent));
    border: var(--dk-rahmen-breite, 1px) solid var(--dk-farbe-rahmen, color-mix(in srgb, currentColor 25%, transparent));
    border-radius: var(--dk-rahmen-radius, 0.375rem);
    padding: 0 0.4rem;
  }

  .dk-termine__wo,
  .dk-termine__anmeldung,
  .dk-termine__mehr {
    margin: 0;
    font-size: var(--dk-groesse-klein, 0.875rem);
    color: var(--dk-farbe-gedaempft, color-mix(in srgb, currentColor 70%, transparent));
  }

  .dk-termine__mehr {
    margin-top: var(--dk-abstand-klein, 0.5rem);
  }

  .dk-termine__link {
    /* Akzent nie als Textfarbe (Ä4/Dunkelmodus): Unterstreichung traegt die
       Auszeichnung, die Farbe kommt von der Site. */
    color: inherit;
    text-decoration: underline;
    text-underline-offset: 0.15em;
  }

  .dk-termine__link:hover {
    text-decoration-thickness: 2px;
  }

  .dk-termine__link:focus-visible {
    outline: 2px solid var(--dk-farbe-akzent, currentColor);
    outline-offset: 2px;
  }

  .dk-termine__hinweis {
    margin: 0;
    color: var(--dk-farbe-gedaempft, color-mix(in srgb, currentColor 70%, transparent));
    font-size: var(--dk-groesse-klein, 0.875rem);
  }

  .dk-termine__hinweis--fehler {
    color: inherit;
  }

  /* ── Darstellung "kompakt": eine Zeile je Termin ─────────────────────── */
  .dk-termine[data-darstellung='kompakt'] .dk-termine__eintrag {
    flex-direction: row;
    flex-wrap: wrap;
    align-items: baseline;
    gap: 0.5rem;
  }

  .dk-termine[data-darstellung='kompakt'] .dk-termine__wann,
  .dk-termine[data-darstellung='kompakt'] .dk-termine__was {
    display: inline-flex;
  }

  /* ── Darstellung "karten": Raster mit Rahmen ─────────────────────────── */
  .dk-termine[data-darstellung='karten'] .dk-termine__liste {
    display: grid;
    grid-template-columns: 1fr;
    gap: var(--dk-abstand-klein, 0.5rem);
  }

  .dk-termine[data-darstellung='karten'] .dk-termine__eintrag {
    border: var(--dk-rahmen-breite, 1px) solid var(--dk-farbe-rahmen, color-mix(in srgb, currentColor 25%, transparent));
    border-radius: var(--dk-rahmen-radius, 0.375rem);
    padding: var(--dk-abstand-klein, 0.5rem) var(--dk-abstand, 0.75rem);
  }

  @media (min-width: 40em) {
    .dk-termine[data-darstellung='karten'] .dk-termine__liste {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .dk-termine * {
      transition: none !important;
      animation: none !important;
    }
  }
</style>
