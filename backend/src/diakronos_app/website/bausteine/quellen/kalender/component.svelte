<section class="dk-kalender" lang="de">
  <h2 class="dk-kalender__titel">{ueberschrift}</h2>

  {#if umschaltbar}
    <div class="dk-kalender__leiste" role="group" aria-label="Ansicht">
      <button
        type="button"
        class="dk-kalender__knopf"
        aria-pressed={ansicht === 'monat'}
        onclick={() => { ansicht_waehlen('monat'); }}
      >{text_monat}</button>
      <button
        type="button"
        class="dk-kalender__knopf"
        aria-pressed={ansicht === 'liste'}
        onclick={() => { ansicht_waehlen('liste'); }}
      >{text_liste}</button>
    </div>
  {/if}

  {#if ladezustand === 'laedt'}
    <p class="dk-kalender__hinweis" role="status">{text_laedt}</p>
  {:else if ladezustand === 'fehler'}
    <p class="dk-kalender__hinweis dk-kalender__hinweis--fehler" role="status">{fehlertext}</p>
  {:else}
    <div class="dk-kalender__steuerung">
      <button type="button" class="dk-kalender__knopf" aria-label="Ein Schritt zurück" onclick={() => { schritt(-1); }}>{text_zurueck}</button>
      <button type="button" class="dk-kalender__knopf" onclick={() => { heute(); }}>{text_heute}</button>
      <button type="button" class="dk-kalender__knopf" aria-label="Ein Schritt vor" onclick={() => { schritt(1); }}>{text_weiter}</button>
    </div>
    <p class="dk-kalender__stand" aria-live="polite">
      <span class="dk-kalender__monat">{titel}</span>
    </p>

    {#if raster_sichtbar}
      <table class="dk-kalender__raster">
        <caption class="dk-kalender__versteckt">{titel}</caption>
        <thead>
          <tr>
            {#each rasterkopf as kopf}
              <th scope="col" abbr={kopf}>{kopf}</th>
            {/each}
          </tr>
        </thead>
        <tbody>
          {#each rasterwochen as woche (woche.schluessel)}
            <tr>
              {#each woche.tage as tag (tag.iso)}
                <td class:heute={tag.heute} class:aussen={!tag.im_monat}>
                  <span class="dk-kalender__tagzahl" aria-hidden="true">{tag.tag}</span>
                  <span class="dk-kalender__versteckt">{tag.tag}. {MONATSNAMEN[tag.monat - 1]}</span>
                  {#if tag.termine.length > 0}
                    <ul class="dk-kalender__tagesliste">
                      {#each tag.termine as termin (termin.id)}
                        <li class="dk-kalender__punkt">
                          <button
                            type="button"
                            class="dk-kalender__eintrag"
                            style:border-left-color={termin.farbe || null}
                            aria-label={termin.vorlesetext}
                            onclick={(ereignis) => { oeffnen(termin.id, ereignis); }}
                            onkeydown={(ereignis) => { taste_am_termin(ereignis, termin.id); }}
                          >{termin.titel}</button>
                          {#if termin.zeit}<span class="dk-kalender__eintragzeit">{termin.zeit}</span>{/if}
                        </li>
                      {/each}
                      {#if tag.weitere > 0}
                        <li class="dk-kalender__mehr">+{tag.weitere} {text_mehr}</li>
                      {/if}
                    </ul>
                  {/if}
                </td>
              {/each}
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}

    <ul class="dk-kalender__liste" hidden={!liste_sichtbar}>
      {#each liste as termin (termin.id)}
        <li class="dk-kalender__listeneintrag">
          <p class="dk-kalender__wann">
            <span class="dk-kalender__dat">{termin.tag}</span>
            {#if termin.zeit}<span class="dk-kalender__zeit">{termin.zeit}</span>{/if}
            {#if termin.zeitraum}<span class="dk-kalender__zeit">– {termin.zeitraum}</span>{/if}
          </p>
          <p class="dk-kalender__was">
            <button
              type="button"
              class="dk-kalender__eintrag dk-kalender__eintrag--liste"
              style:border-left-color={termin.farbe || null}
              aria-label={termin.vorlesetext}
              onclick={(ereignis) => { oeffnen(termin.id, ereignis); }}
              onkeydown={(ereignis) => { taste_am_termin(ereignis, termin.id); }}
            >{termin.titel}</button>
            {#if termin.kategorie}<span class="dk-kalender__kategorie">{termin.kategorie}</span>{/if}
          </p>
          {#if termin.ort}<p class="dk-kalender__wo">{termin.ort}</p>{/if}
        </li>
      {/each}
    </ul>

    {#if anzahl_ansicht === 0}
      <p class="dk-kalender__hinweis" role="status">{leertext}</p>
    {/if}

    {#if detail}
      <div class="dk-kalender__detail" role="region" aria-label={detail.titel}>
        <h3 class="dk-kalender__detailtitel" tabindex="-1" bind:this={detailkopf}>{detail.titel}</h3>
        <p class="dk-kalender__detailzeit"><span>{detail.datum_lang}</span>{#if detail.zeitraum} <span class="dk-kalender__bis">– {detail.zeitraum}</span>{/if}{#if detail.zeit} <span class="dk-kalender__uhr">· {detail.zeit}</span>{/if}</p>
        {#if detail.kategorie}<p class="dk-kalender__kategorie">{detail.kategorie}</p>{/if}
        {#if detail.ort}<p class="dk-kalender__wo">Ort: {detail.ort}</p>{/if}
        {#if detail.beschreibung}<p class="dk-kalender__beschreibung">{detail.beschreibung}</p>{/if}
        {#if detail.anmeldung_url}
          <p><a class="dk-kalender__link" href={detail.anmeldung_url} rel="noopener">{text_anmeldung}</a></p>
        {/if}
        <p><button type="button" class="dk-kalender__knopf" onclick={() => { schliessen(); }}>{text_schliessen}</button></p>
      </div>
    {/if}
  {/if}
</section>

<script>
  // BS-2b: gleiche Bauart wie „Nächste Termine" (BS-2a2): Primo rendert den
  // Block als SERVER-Komponente — Lebenszyklus-Haken sind dort verboten, der Abruf
  // gehört in `$effect` (läuft bei SSR nicht, im Browser einmal beim
  // Einhängen). Die Kalender-Hilfslogik steht bewusst im Block selbst
  // (Primo kopiert Blöcke in Sites; README Regel 1).
  // HINWEIS (Abnahme 07.11.): Primo zerlegt die Datei an JEDEM Stil-Block —
  // in Kommentaren deshalb nie dessen spitze Schreibweise verwenden.
  //
  // NACHARBEIT 08.11. (Review):
  //  * Zeilen: jedes Rasterkind steckt in einer <tr> (vorher lagen die <td>
  //    direkt in <tbody> — ungültig, der Browser ordnet sie fremd an, die
  //    Zellen blieben leer).
  //  * Beide Ansichten werden IMMER gerendert und über das `hidden`-Attribut
  //    geschaltet (dieselbe Technik wie der Steckbrief aus BS-2c). CSS aus dem
  //    Block ist in Primo nicht verlässlich (Regeln kommen in anderer
  //    Reihenfolge, werden umgeschrieben) — `hidden` ist eine Eigenschaft des
  //    Elements und wirkt immer.
  //  * Mobil gilt die Liste (`matchMedia`, Schritt 40 em wie die Site-Regeln).
  //  * Termine im Raster sind Knöpfe: Klick UND Tastatur öffnen das Detail.

  let {
    id,
    ueberschrift = 'Kalender',
    basisadresse = '',
    startansicht = 'monat',
    ansicht_umschaltbar = true,
    kalender = '',
    kategorie = '',
    gruppe = '',
    wochenstart = 'montag',
    farben_kalender = true,
    text_heute = 'Heute',
    text_zurueck = 'Zurück',
    text_weiter = 'Weiter',
    text_monat = 'Monat',
    text_liste = 'Liste',
    text_ganztaegig = 'ganztägig',
    text_anmeldung = 'Zur Anmeldung',
    text_mehr = 'weitere',
    text_laedt = 'Termine werden geladen …',
    leertext = 'In diesem Zeitraum sind keine Termine angekündigt.',
    fehlertext = 'Die Termine sind derzeit nicht abrufbar. Bitte später erneut versuchen.',
    text_schliessen = 'Schließen'
  } = $props();

  const ZEITZONE = 'Europe/Berlin';
  const ZEITLIMIT_MS = 8000;
  /** Ab dieser Breite gilt „breit" (wie die Site-Regeln der Vorlage). */
  const BREIT_AB = '40em';
  /** Höchstzahl sichtbarer Termine je Rasterzelle; der Rest steht als „+n". */
  const ZELLE_MAX = 3;
  const MONATSNAMEN = ['Januar', 'Februar', 'März', 'April', 'Mai', 'Juni', 'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember'];
  const WOCHENTAGE_KURZ = ['So', 'Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa'];
  const WOCHENTAGE_LANG = ['Sonntag', 'Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag'];

  /** „monat" oder „liste" — der Startwert der Ansicht (Vorgabefeld). */
  function unterseite_ansicht(wert) {
    return String(wert || '').trim() === 'liste' ? 'liste' : 'monat';
  }

  /**
   * Startansicht: sie wird EINMAL ausgewertet (sie ist eine Vorgabe, kein
   * Zustand) — danach führt die Umschaltung den Zustand.
   */
  let ansicht = $state(unterseite_ansicht(startansicht)); // Beabsichtigt: Startwert, danach führt der Zustand.
  /** @type {'laedt' | 'fertig' | 'fehler'} */
  let ladezustand = $state('laedt');
  /** @type {Array<object>} */
  let termine = $state([]);
  /** @type {object | null} */
  let detail = $state(null);
  /** @type {HTMLElement | undefined} */
  let detailkopf = $state();
  /** @type {HTMLElement | null} */
  let ausloeser = null;
  /** Schmal genug für die Liste? (nur im Browser ermittelt) */
  let ist_schmal = $state(false);

  // Gezeigter Monat (naiv: Jahr + Monat), Start beim heutigen Tag.
  const jetzt = new Date();
  const jetzt_teile = teile(jetzt);
  let zeige_jahr = $state(Number(jetzt_teile.jahr));
  let zeige_monat = $state(Number(jetzt_teile.monat));
  let heute_iso = jetzt_teile.jahr + '-' + jetzt_teile.monat + '-' + jetzt_teile.tag;
  let monat_schluessel = $derived(
    String(zeige_jahr).padStart(4, '0') + '-' + String(zeige_monat).padStart(2, '0')
  );

  let umschaltbar = $derived(ansicht_umschaltbar !== false);
  let titel = $derived(MONATSNAMEN[zeige_monat - 1] + ' ' + zeige_jahr);
  let rasterkopf = $derived(raster_kopf(wochenstart));
  /** Ein Termin als Anzeigezeile (Funktion, damit Markup UND Detail dieselbe Form nutzen). */
  let alle_liste = $derived(
    termine
      .map((eintrag) => anzeige_zeile(eintrag))
      .filter((zeile) => zeile.iso >= heute_iso)
      .sort((a, b) => (a.sortierung < b.sortierung ? -1 : a.sortierung > b.sortierung ? 1 : 0))
  );
  let liste = $derived(alle_liste.filter((zeile) => zeile.iso.slice(0, 7) === monat_schluessel));

  // ── Ansichten ────────────────────────────────────────────────────────────
  /** Im Raster sichtbar? Mobil nie (die Liste trägt dort die Termine). */
  let raster_sichtbar = $derived(ansicht === 'monat' && !ist_schmal);
  /** Als Liste sichtbar? Mobil immer — das 7-Spalten-Raster ist dort unlesbar. */
  let liste_sichtbar = $derived(ansicht === 'liste' || ist_schmal);
  /** Leertext: die Termine der GEZEIGTEN Ansicht (nicht die der Zukunft). */
  let anzahl_ansicht = $derived(raster_sichtbar ? termine.length : liste.length);
  /** Das Raster, nach Wochen geteilt: eine <tr> je Woche, darin sieben <td>. */
  let rasterwochen = $derived(wochen(monatsraster(zeige_jahr, zeige_monat, wochenstart, heute_iso), termine));

  // ── Hilfslogik (siehe kalender/kalenderlogik.mjs) ────────────────────────
  function zahl(wert, vorgabe, minimum, maximum) {
    const geprueft = Number(String(wert === null || wert === undefined ? '' : wert).replace(',', '.'));
    if (!Number.isFinite(geprueft)) return vorgabe;
    return Math.min(maximum, Math.max(minimum, Math.trunc(geprueft)));
  }

  function kennungen(wert) {
    return String(wert || '').split(',').map((teil) => teil.trim()).filter((teil) => teil !== '');
  }

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
   * Anmeldeadresse eines Termins (wie die Anmeldung aus BS-2c).
   *
   * Die Lese-API liefert sie RELATIV, wenn in Diakronos keine öffentliche
   * Adresse gepflegt ist (`/diakonos/gast?token=…`) — dann kommt der Ursprung
   * von Diakronos davor. Eine absolute http(s)-Adresse bleibt unverändert;
   * alles andere (z. B. `javascript:`) fällt auf `""`, der Link entfällt.
   */
  function anmelde_adresse(wert) {
    const text = String(wert || '').trim();
    if (text === '') return '';
    if (/^https?:\/\//i.test(text)) return nur_webadresse(text);
    const basiswert = basis();
    if (basiswert === '' || !text.startsWith('/')) return '';
    try {
      const ziel = new URL(text, basiswert + '/');
      const basis_teile = new URL(basiswert);
      const basis_pfad = basis_teile.pathname.replace(/\/+$/, '');
      if (basis_pfad !== '' && ziel.pathname.startsWith(basis_pfad + '/')) {
        // Der Pfad trägt den Präfix bereits: Zielpfad OHNE ihn anhängen.
        const rest = ziel.pathname.slice(basis_pfad.length);
        return basiswert + rest + ziel.search;
      }
      return basis_teile.origin + ziel.pathname + ziel.search;
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

  function tagestext(iso) {
    const treffer = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(iso || '').trim());
    if (!treffer) return '';
    const nummer = new Date(Date.UTC(Number(treffer[1]), Number(treffer[2]) - 1, Number(treffer[3]))).getUTCDay();
    return WOCHENTAGE_KURZ[nummer] + '., ' + treffer[3] + '.' + treffer[2] + '.';
  }

  function tagestext_lang(iso) {
    const treffer = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(iso || '').trim());
    if (!treffer) return '';
    const jahr = Number(treffer[1]);
    const monat = Number(treffer[2]);
    const tag = Number(treffer[3]);
    const nummer = new Date(Date.UTC(jahr, monat - 1, tag)).getUTCDay();
    return WOCHENTAGE_LANG[nummer] + ', ' + tag + '. ' + MONATSNAMEN[monat - 1] + ' ' + jahr;
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

  function ende_text(beginn, ende) {
    const start = als_datum(beginn);
    const ende_datum = als_datum(ende);
    if (ende_datum === null) return '';
    if (start !== null && isodatum(start) === isodatum(ende_datum)) return '';
    return tagestext(isodatum(ende_datum));
  }

  function zeitangabe(eintrag) {
    if (!eintrag || typeof eintrag !== 'object') return '';
    if (eintrag.ganztaegig === true) return String(text_ganztaegig || '');
    return zeitfenster(eintrag.beginn, eintrag.ende);
  }

  function termine_je_tag(eintraege) {
    const karte = new Map();
    for (const eintrag of Array.isArray(eintraege) ? eintraege : []) {
      if (!eintrag || typeof eintrag !== 'object') continue;
      const beginn = als_datum(eintrag.beginn);
      if (beginn === null) continue;
      const schluessel = isodatum(beginn);
      if (!karte.has(schluessel)) karte.set(schluessel, []);
      karte.get(schluessel).push(eintrag);
    }
    return karte;
  }

  function farbe_wert(wert) {
    const text = String(wert || '').trim();
    if (/^#[0-9a-f]{3,8}$/i.test(text)) return text;
    if (/^(rgb|rgba|hsl|hsla)\(\s*[0-9%,.\s/]+\)$/i.test(text)) return text;
    return '';
  }

  /** Tage eines Monats (Monat 1..12) — Schaltjahre nach gregorianischer Regel. */
  function tage_im_monat(jahr, monat) {
    return new Date(Date.UTC(jahr, monat, 0)).getUTCDate();
  }

  /** „2026-10-31“ — das Abruffenster ist der volle Monat, nicht das Raster. */
  function zeitraum_ein_monat(jahr, monat) {
    const monatstext = String(monat).padStart(2, '0');
    return {
      von: String(jahr).padStart(4, '0') + '-' + monatstext + '-01',
      bis: String(jahr).padStart(4, '0') + '-' + monatstext + '-' + String(tage_im_monat(jahr, monat)).padStart(2, '0')
    };
  }

  /** Rastertage in Wochen geteilt (eine <tr> je Woche, sieben <td>). */
  function raster_wochen(tage) {
    const liste = Array.isArray(tage) ? tage : [];
    const wochen = [];
    for (let i = 0; i < liste.length; i += 7) {
      const woche = liste.slice(i, i + 7);
      if (woche.length === 0) continue;
      wochen.push({ schluessel: (woche[0] && woche[0].iso) || String(i), tage: woche });
    }
    return wochen;
  }

  /** Höchstens `max` Termine je Zelle; der Rest wird als Zahl gezeigt. */
  function zelle_aufteilen(eintraege, max) {
    const liste = Array.isArray(eintraege) ? eintraege : [];
    const grenze = Math.max(1, Math.trunc(max) || ZELLE_MAX);
    // Kann die Zelle ALLE ihre Termine zeigen, entfaellt die Kuerzung ganz —
    // dann steht oben der Zeitzusatz („<n> Termine“), sonst waere „1 Termin“
    // und „+0 weitere“ doppelt gemeldet.
    if (liste.length <= grenze) return { termine: liste, weitere: 0 };
    return { termine: liste.slice(0, grenze), weitere: liste.length - grenze };
  }

  /** Gilt die Antwort dieses Abrufs noch (schnelles Blättern)? */
  function abruf_ist_aktuell(meine, aktuell) {
    return Number(meine) === Number(aktuell);
  }

  function wochenstart_nummer(wert) {
    return String(wert || '').trim().toLowerCase() === 'sonntag' ? 0 : 1;
  }

  function wochenstart_von(datum, wert) {
    const start = wochenstart_nummer(wert);
    const kopie = new Date(Date.UTC(datum.getUTCFullYear(), datum.getUTCMonth(), datum.getUTCDate()));
    kopie.setUTCDate(kopie.getUTCDate() - ((kopie.getUTCDay() - start + 7) % 7));
    return kopie;
  }

  function monatsraster(jahr, monat, wert, heute) {
    const erster = new Date(Date.UTC(jahr, monat - 1, 1));
    const letzter = new Date(Date.UTC(jahr, monat - 1, tage_im_monat(jahr, monat)));
    const von = wochenstart_von(erster, wert);
    const bis = wochenstart_von(letzter, wert);
    bis.setUTCDate(bis.getUTCDate() + 6);
    const tage = [];
    for (let zeit = von.getTime(); zeit <= bis.getTime(); zeit += 86400000) {
      const tag = new Date(zeit);
      const j = tag.getUTCFullYear();
      const m = tag.getUTCMonth() + 1;
      const t = tag.getUTCDate();
      const iso = [String(j).padStart(4, '0'), String(m).padStart(2, '0'), String(t).padStart(2, '0')].join('-');
      tage.push({ jahr: j, monat: m, tag: t, iso, im_monat: j === jahr && m === monat, heute: iso === heute });
    }
    return tage;
  }

  function raster_kopf(wert) {
    const start = wochenstart_nummer(wert);
    return Array.from({ length: 7 }, (_, i) => WOCHENTAGE_KURZ[(start + i) % 7]);
  }

  /**
   * Die Rastertage in Wochen geteilt: `[{ schluessel, tage: [ … ] }]`.
   *
   * Ein <table> verlangt <tr> zwischen <tbody> und <td>; und jeder Tag trägt
   * seine Termine schon hier (statt sie im Markup zu filtern).
   */
  function wochen(tage, eintraege) {
    const je_tag = termine_je_tag(eintraege);
    const mit_terminen = tage.map((tag) => {
      const gefunden = (je_tag.get(tag.iso) || [])
        .map((eintrag) => anzeige_zeile(eintrag))
        .sort((a, b) => (a.sortierung < b.sortierung ? -1 : a.sortierung > b.sortierung ? 1 : 0));
      return { ...tag, ...zelle_aufteilen(gefunden, ZELLE_MAX) };
    });
    return raster_wochen(mit_terminen);
  }

  /** Ein Termin als Anzeigezeile. Farbe nur, wenn das Kalenderfeld sie hergibt. */
  function anzeige_zeile(eintrag) {
    const beginn = als_datum(eintrag.beginn);
    const iso = beginn === null ? '' : isodatum(beginn);
    const zeit = zeitangabe(eintrag);
    const titel_text = String(eintrag.titel || '').trim();
    return {
      id: String(eintrag.id || '') || iso + titel_text,
      iso,
      sortierung: beginn === null ? '' : String(beginn.getTime()).padStart(20, '0') + String(eintrag.titel || ''),
      tag: tagestext(iso),
      zeitraum: ende_text(eintrag.beginn, eintrag.ende),
      datum_lang: tagestext_lang(iso),
      titel: titel_text,
      zeit,
      ort: String(eintrag.ort || '').trim(),
      kategorie: String(eintrag.kategorie || '').trim(),
      beschreibung: String(eintrag.beschreibung || '').trim(),
      anmeldung_url: anmelde_adresse(eintrag.anmeldung_url),
      farbe: farben_kalender === false ? '' : farbe_wert(eintrag.farbe),
      vorlesetext: [tagestext_lang(iso), zeit, titel_text].filter((t) => t !== '').join(', ')
    };
  }

  // ── Steuerung ───────────────────────────────────────────────────────────
  /**
   * Ein Schritt zurück/vor. In BEIDEN Ansichten ist der Schritt ein Monat:
   * der Stand besteht aus Monat und Jahr, damit „Heute" und der Titel in
   * Monats- wie Listenansicht dasselbe bedeuten.
   */
  function schritt(richtung) {
    const naechster = monat_verschieben(zeige_jahr, zeige_monat, richtung);
    zeige_jahr = naechster.jahr;
    zeige_monat = naechster.monat;
  }

  /** Monat um `richtung` verschoben (Jahr läuft mit; -1 zurück, +1 vor). */
  function monat_verschieben(jahr, monat, richtung) {
    const gesamt = jahr * 12 + (monat - 1) + Math.trunc(richtung);
    return { jahr: Math.floor(gesamt / 12), monat: (gesamt % 12 + 12) % 12 + 1 };
  }

  function heute() {
    const gleich = teile(new Date());
    zeige_jahr = Number(gleich.jahr);
    zeige_monat = Number(gleich.monat);
  }

  /** Ein Monat, zwei Ansichten — Schlüssel für den Abruf-Cache. */
  function stand_schluessel() {
    return zeitraum_ein_monat(zeige_jahr, zeige_monat);
  }

  function ansicht_waehlen(naechste) {
    if (ansicht === naechste) return;
    if (detail !== null) schliessen(false);
    ansicht = naechste;
  }

  /** Detail öffnen: Auslöser merken, Fokus auf die Überschrift. */
  function oeffnen(idwert, ereignis) {
    const gefunden = termine.find((eintrag) => String(eintrag.id || '') === String(idwert));
    if (!gefunden) return;
    ausloeser = (ereignis && ereignis.currentTarget) || null;
    detail = anzeige_zeile(gefunden);
    const ziel = detail;
    // Erst wenn der Detailknoten im Dokument steht, darf der Fokus wandern
    // (Effekt-Reihenfolge in Svelte 5: ein Effekt über einem {#if} sieht den
    // neuen Zweig noch nicht).
    (async () => {
      await Promise.resolve();
      await Promise.resolve();
      if (detail !== ziel) return;
      if (detailkopf && typeof detailkopf.focus === 'function') detailkopf.focus();
    })();
  }

  /**
   * Taste am Termin: Enter/Space öffnet das Detail.
   *
   * Ein Browser ohne funktionierende Knopf-Aktivierung (Kopier-/SSR-Spielarten,
   * Abnahme-Umgebung) täte hier sonst nichts; der Klick-Handler bleibt für
   * Maus und Zeigegeräte. Space wird abgefangen, damit die Seite nicht
   * scrollt.
   */
  function taste_am_termin(ereignis, idwert) {
    if (!ereignis || (ereignis.key !== 'Enter' && ereignis.key !== ' ' && ereignis.key !== 'Spacebar')) return;
    ereignis.preventDefault();
    oeffnen(idwert, ereignis);
  }

  /** Detail schließen; Fokus zurück zum Termin, der es geöffnet hat. */
  function schliessen(zurueck_springen = true) {
    const ziel = ausloeser;
    ausloeser = null;
    detail = null;
    if (!zurueck_springen || !ziel || typeof ziel.focus !== 'function') return;
    // Erst nach dem Rendern: der Knopf muss wieder sichtbar sein, sonst
    // nimmt der Browser den Fokus nicht an. `setTimeout(0)` läuft nach dem
    // Anwenden aller Svelte-Mikrotasks (Prüfseite: 08.11.).
    if (typeof setTimeout !== 'function') return;
    setTimeout(() => {
      if (detail !== null) return;
      ziel.focus();
    }, 0);
  }

  function taste_im_detail(ereignis) {
    if (ereignis.key === 'Escape' && detail !== null) {
      ereignis.preventDefault();
      schliessen();
    }
  }

  // ── Daten holen ─────────────────────────────────────────────────────────
  function abfrageadresse() {
    const basiswert = basis();
    if (basiswert === '') return '';
    const zeitraum = stand_schluessel();
    const parameter = new URLSearchParams();
    parameter.set('von', zeitraum.von);
    parameter.set('bis', zeitraum.bis);
    parameter.set('limit', '500');
    const kalenderliste = kennungen(kalender);
    if (kalenderliste.length > 0) parameter.set('kalender', kalenderliste.join(','));
    const kategorie_wert = String(kategorie || '').trim();
    if (kategorie_wert !== '') parameter.set('kategorie', kategorie_wert);
    const gruppe_wert = String(gruppe || '').trim();
    if (gruppe_wert !== '') parameter.set('gruppe', gruppe_wert);
    return basiswert + '/website/oeffentlich/termine?' + parameter.toString();
  }

  /**
   * Laufende Nummer je Abruf: nur die Antwort des JÜNGSTEN Abrufs zählt.
   * Beim schnellen Blättern (September -> Oktober -> November) kann eine alte
   * Antwort später eintreffen; sie darf den gezeigten Monat nicht überschreiben.
   */
  let abruf_nr = 0;

  async function laden() {
    const adresse = abfrageadresse();
    if (adresse === '') {
      ladezustand = 'fehler';
      return;
    }
    const meine = ++abruf_nr;
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
      if (!abruf_ist_aktuell(meine, abruf_nr)) return;
      if (!antwort.ok) throw new Error('HTTP ' + antwort.status);
      const koerper = await antwort.json();
      if (!abruf_ist_aktuell(meine, abruf_nr)) return;
      if (!koerper || typeof koerper !== 'object' || !('message' in koerper)) throw new Error('Antwortform');
      termine = Array.isArray(koerper.message) ? koerper.message : [];
      ladezustand = 'fertig';
    } catch (fehler) {
      if (!abruf_ist_aktuell(meine, abruf_nr)) return;
      termine = [];
      ladezustand = 'fehler';
    } finally {
      if (wecker !== null) clearTimeout(wecker);
    }
  }

  // Monatswechsel: ab dem Monat des STARTMONATS laden (der Startmonat ist
  // gezeigt, sobald der Block im Browser eingehängt ist).
  let geladener_monat = '';
  $effect(() => {
    const stand = stand_schluessel();
    const schluessel = stand.von + '…' + stand.bis;
    if (schluessel === geladener_monat) return;
    geladener_monat = schluessel;
    void laden();
  });

  // Breite beobachten (nur im Browser; bei SSR gibt es kein window).
  $effect(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return;
    const abfrage = window.matchMedia('(min-width: ' + BREIT_AB + ')');
    const uebernehmen = () => { ist_schmal = !abfrage.matches; };
    uebernehmen();
    if (typeof abfrage.addEventListener === 'function') {
      abfrage.addEventListener('change', uebernehmen);
      return () => abfrage.removeEventListener('change', uebernehmen);
    }
    return;
  });

  // Escape schließt das Detail (Fokus zurück zum Termin).
  $effect(() => {
    if (typeof window === 'undefined' || detail === null) return;
    const zuhoerer = (ereignis) => { taste_im_detail(ereignis); };
    window.addEventListener('keydown', zuhoerer);
    return () => window.removeEventListener('keydown', zuhoerer);
  });

</script>

<style>
  /* --dk-* NUR LESEN, nie deklarieren (BS-0 F5). Dunkelmodus: Farben werden
     geerbt, Text-Farbe kommt von der Site („Weg 1", BS-2a). */
  .dk-kalender {
    color: var(--dk-farbe-text, inherit);
    background: var(--dk-farbe-flaeche, transparent);
    font-family: var(--dk-schrift, inherit);
    font-size: var(--dk-groesse-text, 1rem);
    box-sizing: border-box;
    padding: var(--dk-abstand, 0.75rem) 0;
    border-top: var(--dk-rahmen-breite, 1px) solid var(--dk-farbe-rahmen, color-mix(in srgb, currentColor 25%, transparent));
  }

  .dk-kalender *,
  .dk-kalender *::before,
  .dk-kalender *::after {
    box-sizing: border-box;
  }

  /* Aus/Ausgeblendet: `hidden` ist die Schaltung selbst; die Regel hält sie
     fest, weil Site-Stile `display` für Listen/Tabellen setzen können. */
  .dk-kalender [hidden] {
    display: none !important;
  }

  .dk-kalender__titel {
    margin: 0 0 var(--dk-abstand, 0.75rem);
    font-family: var(--dk-schrift-ueberschrift, var(--dk-schrift, inherit));
    font-size: var(--dk-groesse-ueberschrift, 1.375rem);
    line-height: 1.25;
  }

  .dk-kalender__leiste,
  .dk-kalender__steuerung {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
    align-items: center;
    margin-bottom: var(--dk-abstand-klein, 0.5rem);
  }

  .dk-kalender__knopf {
    font: inherit;
    font-size: var(--dk-groesse-klein, 0.875rem);
    color: inherit;
    background: transparent;
    border: var(--dk-rahmen-breite, 1px) solid var(--dk-farbe-rahmen, color-mix(in srgb, currentColor 25%, transparent));
    border-radius: var(--dk-rahmen-radius, 0.375rem);
    padding: 0.3rem 0.6rem;
    cursor: pointer;
  }

  .dk-kalender__knopf:hover {
    border-color: var(--dk-farbe-akzent, currentColor);
  }

  .dk-kalender__knopf:focus-visible {
    outline: 2px solid var(--dk-farbe-akzent, currentColor);
    outline-offset: 2px;
  }

  .dk-kalender__knopf[aria-pressed='true'] {
    border-width: 2px;
    border-color: var(--dk-farbe-akzent, currentColor);
    font-weight: 600;
  }

  .dk-kalender__stand {
    margin: 0 0 var(--dk-abstand-klein, 0.5rem);
    font-weight: 600;
  }

  .dk-kalender__versteckt {
    position: absolute;
    width: 1px;
    height: 1px;
    margin: -1px;
    padding: 0;
    overflow: hidden;
    clip: rect(0 0 0 0);
    white-space: nowrap;
    border: 0;
  }

  /* Monatsraster */
  .dk-kalender__raster {
    width: 100%;
    border-collapse: collapse;
    table-layout: fixed;
  }

  .dk-kalender__raster th {
    font-size: var(--dk-groesse-klein, 0.875rem);
    font-weight: 600;
    text-align: left;
    padding: 0.25rem 0.2rem;
    color: var(--dk-farbe-gedaempft, color-mix(in srgb, currentColor 70%, transparent));
  }

  .dk-kalender__raster td {
    vertical-align: top;
    border: var(--dk-rahmen-breite, 1px) solid var(--dk-farbe-rahmen, color-mix(in srgb, currentColor 25%, transparent));
    padding: 0.2rem;
    height: 4.5rem;
  }

  .dk-kalender__raster td.aussen {
    opacity: 0.55;
  }

  .dk-kalender__raster td.heute {
    outline: 2px solid var(--dk-farbe-akzent, currentColor);
    outline-offset: -2px;
  }

  .dk-kalender__tagzahl {
    display: block;
    font-size: var(--dk-groesse-klein, 0.875rem);
    font-weight: 600;
  }

  .dk-kalender__tagesliste {
    margin: 0;
    padding: 0;
    list-style: none;
  }

  .dk-kalender__punkt {
    margin: 0.1rem 0;
  }

  .dk-kalender__eintrag {
    font: inherit;
    font-size: var(--dk-groesse-klein, 0.875rem);
    color: inherit;
    background: transparent;
    border: 0;
    border-left: 3px solid var(--dk-farbe-akzent, currentColor);
    padding: 0 0 0 0.25rem;
    margin: 0;
    text-align: left;
    cursor: pointer;
    display: block;
    width: 100%;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .dk-kalender__eintragzeit {
    display: block;
    padding-left: 0.45rem;
    font-size: var(--dk-groesse-klein, 0.875rem);
    color: var(--dk-farbe-gedaempft, color-mix(in srgb, currentColor 70%, transparent));
  }

  .dk-kalender__eintrag:hover {
    text-decoration: underline;
  }

  .dk-kalender__eintrag:focus-visible {
    outline: 2px solid var(--dk-farbe-akzent, currentColor);
    outline-offset: 1px;
  }

  .dk-kalender__mehr {
    font-size: var(--dk-groesse-klein, 0.875rem);
    color: var(--dk-farbe-gedaempft, color-mix(in srgb, currentColor 70%, transparent));
  }

  /* Listenansicht */
  .dk-kalender__liste {
    margin: 0;
    padding: 0;
    list-style: none;
  }

  /* Im Breitmodus (Umschaltung auf Liste) steht unter der Steuerung kein
     Raster mehr — Abstand zum Monatstitel. */
  @media (min-width: 40em) {
    .dk-kalender__liste {
      margin-top: var(--dk-abstand-klein, 0.5rem);
    }
  }

  .dk-kalender__listeneintrag {
    padding: var(--dk-abstand-klein, 0.5rem) 0;
    border-bottom: var(--dk-rahmen-breite, 1px) solid var(--dk-farbe-rahmen, color-mix(in srgb, currentColor 25%, transparent));
  }

  .dk-kalender__wann,
  .dk-kalender__was {
    margin: 0;
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    align-items: baseline;
  }

  .dk-kalender__dat {
    font-weight: 600;
  }

  .dk-kalender__zeit,
  .dk-kalender__wo,
  .dk-kalender__kategorie {
    font-size: var(--dk-groesse-klein, 0.875rem);
    color: var(--dk-farbe-gedaempft, color-mix(in srgb, currentColor 70%, transparent));
  }

  .dk-kalender__eintrag--liste {
    font-weight: 600;
    border-left: 3px solid var(--dk-farbe-akzent, currentColor);
    width: auto;
    white-space: normal;
  }

  /* Detail */
  .dk-kalender__detail {
    margin-top: var(--dk-abstand, 0.75rem);
    padding: var(--dk-abstand, 0.75rem);
    border: var(--dk-rahmen-breite, 1px) solid var(--dk-farbe-rahmen, color-mix(in srgb, currentColor 25%, transparent));
    border-radius: var(--dk-rahmen-radius, 0.375rem);
  }

  .dk-kalender__detailtitel {
    margin: 0 0 0.25rem;
    font-size: var(--dk-groesse-ueberschrift, 1.375rem);
  }

  .dk-kalender__detailtitel:focus-visible {
    outline: 2px solid var(--dk-farbe-akzent, currentColor);
    outline-offset: 2px;
  }

  .dk-kalender__detailzeit {
    margin: 0 0 0.25rem;
    font-weight: 600;
  }

  .dk-kalender__beschreibung {
    white-space: pre-line;
  }

  .dk-kalender__link {
    color: inherit;
    text-decoration: underline;
    text-underline-offset: 0.15em;
  }

  .dk-kalender__hinweis {
    margin: 0;
    font-size: var(--dk-groesse-klein, 0.875rem);
    color: var(--dk-farbe-gedaempft, color-mix(in srgb, currentColor 70%, transparent));
  }
</style>
