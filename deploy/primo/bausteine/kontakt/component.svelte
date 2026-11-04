<section class="dk-kontakt" lang="de">
  <h2 class="dk-kontakt__titel">{ueberschrift}</h2>
  {#if einleitung}<p class="dk-kontakt__einleitung">{einleitung}</p>{/if}

  {#if zustand === 'gesendet'}
    <p class="dk-kontakt__status dk-kontakt__status--ok" role="status">{erfolgstext}</p>
  {:else}
    {#if zustand === 'fehler'}
      <p class="dk-kontakt__status dk-kontakt__status--fehler" role="alert">{fehlermeldung}</p>
    {/if}

    <form class="dk-kontakt__formular" novalidate onsubmit={absenden}>
      <div class="dk-kontakt__feld">
        <label class="dk-kontakt__label" for={id_name}>{text_name}</label>
        <input
          class="dk-kontakt__eingabe"
          id={id_name}
          name="name"
          type="text"
          autocomplete="name"
          maxlength="120"
          required
          aria-describedby={fehler.name ? id_name + '-fehler' : undefined}
          aria-invalid={fehler.name ? 'true' : undefined}
          bind:value={name}
        />
        {#if fehler.name}<p class="dk-kontakt__feldhinweis" id={id_name + '-fehler'}>{fehler.name}</p>{/if}
      </div>

      <div class="dk-kontakt__feld">
        <label class="dk-kontakt__label" for={id_email}>{text_email}</label>
        <input
          class="dk-kontakt__eingabe"
          id={id_email}
          name="email"
          type="email"
          inputmode="email"
          autocomplete="email"
          maxlength="200"
          required
          aria-describedby={fehler.email ? id_email + '-fehler' : undefined}
          aria-invalid={fehler.email ? 'true' : undefined}
          bind:value={email}
        />
        {#if fehler.email}<p class="dk-kontakt__feldhinweis" id={id_email + '-fehler'}>{fehler.email}</p>{/if}
      </div>

      {#if postfach_auswahl && postfaecher.length > 0}
        <div class="dk-kontakt__feld">
          <label class="dk-kontakt__label" for={id_postfach}>{text_postfach}</label>
          <select class="dk-kontakt__eingabe" id={id_postfach} name="postfach" bind:value={postfach_gewaehlt}
            aria-describedby={fehler.postfach ? id_postfach + '-fehler' : undefined}
            aria-invalid={fehler.postfach ? 'true' : undefined}>
            {#each postfaecher as eintrag (eintrag.slug)}
              <option value={eintrag.slug}>{eintrag.bezeichnung}</option>
            {/each}
          </select>
          {#if fehler.postfach}<p class="dk-kontakt__feldhinweis" id={id_postfach + '-fehler'}>{fehler.postfach}</p>{/if}
        </div>
      {/if}

      <div class="dk-kontakt__feld">
        <label class="dk-kontakt__label" for={id_nachricht}>{text_nachricht}</label>
        <textarea
          class="dk-kontakt__eingabe dk-kontakt__eingabe--mehrzeilig"
          id={id_nachricht}
          name="nachricht"
          rows="6"
          maxlength="5000"
          required
          aria-describedby={fehler.nachricht ? id_nachricht + '-fehler' : undefined}
          aria-invalid={fehler.nachricht ? 'true' : undefined}
          bind:value={nachricht}
        ></textarea>
        {#if fehler.nachricht}<p class="dk-kontakt__feldhinweis" id={id_nachricht + '-fehler'}>{fehler.nachricht}</p>{/if}
      </div>

      <!-- Honeypot: fuer Menschen unsichtbar, fuer Bots ein ausgefuelltes Feld. -->
      <div class="dk-kontakt__honig" aria-hidden="true">
        <label for={id_honig}>Bitte dieses Feld leer lassen</label>
        <input id={id_honig} name="website" type="text" tabindex="-1" autocomplete="off" bind:value={honig} />
      </div>

      <div class="dk-kontakt__feld dk-kontakt__feld--einwilligung">
        <input
          class="dk-kontakt__kaestchen"
          id={id_einwilligung}
          name="einwilligung"
          type="checkbox"
          required
          aria-describedby={fehler.einwilligung ? id_einwilligung + '-fehler' : undefined}
          aria-invalid={fehler.einwilligung ? 'true' : undefined}
          bind:checked={einwilligung_erteilt}
        />
        <label class="dk-kontakt__label dk-kontakt__label--kaestchen" for={id_einwilligung}>
          {einwilligung}
          {#if datenschutz_adresse}
            <a class="dk-kontakt__link" href={datenschutz_adresse} rel="noopener">{datenschutz_text}</a>
          {/if}
        </label>
        {#if fehler.einwilligung}<p class="dk-kontakt__feldhinweis" id={id_einwilligung + '-fehler'}>{fehler.einwilligung}</p>{/if}
      </div>

      <p class="dk-kontakt__absenden">
        <button class="dk-kontakt__knopf" type="submit" disabled={zustand === 'sendet'}>
          {zustand === 'sendet' ? text_sendet : button_text}
        </button>
      </p>
    </form>
  {/if}
</section>

<script>
  // BS-2a2 (Abnahme-Befund): Primo rendert Abschnitte mit `svelte/server` —
  // `onMount` ist dort verboten („lifecycle_outside_component"), der Publish
  // bricht ab. Der Abruf der Postfaecher laeuft deshalb in `$effect` (bei SSR
  // aus, im Browser einmal beim Einhaengen; der Effekt liest keine Abhaengigkeit).

  let {
    ueberschrift = 'Kontakt',
    einleitung = '',
    basisadresse = '',
    postfach = '',
    postfach_auswahl = false,
    einwilligung = 'Ich bin damit einverstanden, dass meine Angaben zur Beantwortung meiner Anfrage verwendet werden.',
    datenschutz_url = '',
    datenschutz_text = 'Datenschutzhinweise',
    text_name = 'Ihr Name',
    text_email = 'Ihre E-Mail-Adresse',
    text_postfach = 'An wen richtet sich Ihre Nachricht?',
    text_nachricht = 'Ihre Nachricht',
    text_sendet = 'Wird gesendet …',
    text_postfach_fehler = 'Bitte wählen Sie eines aus der Liste.',
    text_postfach_fehler_server = 'Dieses Postfach gibt es nicht. Bitte wählen Sie eines aus der Liste.',
    text_adresse_fehlt = 'Das Formular ist nicht eingerichtet (Diakronos-Adresse fehlt).',
    text_rate_limit = 'Es wurden gerade viele Nachrichten gesendet. Bitte versuchen Sie es später erneut.',
    button_text = 'Nachricht senden',
    erfolgstext = 'Vielen Dank! Ihre Nachricht ist angekommen.',
    fehlertext = 'Die Nachricht konnte nicht gesendet werden. Bitte versuchen Sie es später erneut.'
  } = $props();

  /** @type {'bereit' | 'sendet' | 'gesendet' | 'fehler'} */
  let zustand = $state('bereit');
  /** @type {string} */
  let fehlermeldung = $state('');

  let name = $state('');
  let email = $state('');
  let nachricht = $state('');
  let honig = $state('');
  let einwilligung_erteilt = $state(false);
  /** @type {Array<{slug: string, bezeichnung: string}>} */
  let postfaecher = $state([]);
  let postfach_gewaehlt = $state('');

  /** @type {Record<string, string>} */
  let fehler = $state({});

  // Eindeutige Feldkennungen: zwei Kontaktformulare auf EINER Seite wuerden
  // sich sonst die IDs teilen und die Labels auf das falsche Feld zeigen.
  const stamm = 'dk-kontakt-' + Math.random().toString(36).slice(2, 8) + '-';
  const id_name = stamm + 'name';
  const id_email = stamm + 'email';
  const id_nachricht = stamm + 'nachricht';
  const id_einwilligung = stamm + 'einwilligung';
  const id_postfach = stamm + 'postfach';
  const id_honig = stamm + 'honig';

  const ZEITLIMIT_MS = 15000;
  const NAME_MAX = 120;
  const EMAIL_MAX = 200;
  const NACHRICHT_MAX = 5000;

  let datenschutz_adresse = $derived(nur_webadresse(datenschutz_url));

  // ── Hilfslogik (bewusst je Baustein eigenstaendig, siehe README Regel 1) ──
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

  /** Adresse des Kontakt-Endpunkts (POST, allow_guest). */
  function sendeadresse() {
    const basiswert = basis();
    return basiswert === '' ? '' : basiswert + '/api/method/website.kontakt_senden';
  }

  /** Postfach-Liste der öffentlichen API (nur aktive, ohne Adressen). */
  function listenadresse() {
    const basiswert = basis();
    return basiswert === '' ? '' : basiswert + '/website/oeffentlich/postfaecher';
  }

  /** E-Mail-Adresse: eine Pruefung, die auch der Server macht (grob, de-DE). */
  function email_gueltig(wert) {
    const text = String(wert || '').trim();
    if (text === '' || text.length > EMAIL_MAX) return false;
    if (/\s/.test(text)) return false;
    const at = text.indexOf('@');
    if (at <= 0 || at !== text.lastIndexOf('@')) return false;
    const domain = text.slice(at + 1);
    return domain.includes('.') && !domain.startsWith('.') && !domain.endsWith('.');
  }

  /** Feldpruefung wie auf dem Server: eine deutsche Meldung je Feld. */
  function pruefen() {
    /** @type {Record<string, string>} */
    const gefunden = {};
    if (String(name || '').trim() === '') {
      gefunden.name = 'Bitte geben Sie Ihren Namen an.';
    } else if (String(name).trim().length > NAME_MAX) {
      gefunden.name = 'Der Name ist zu lang.';
    }
    if (String(email || '').trim() === '') {
      gefunden.email = 'Bitte geben Sie Ihre E-Mail-Adresse an.';
    } else if (!email_gueltig(email)) {
      gefunden.email = 'Bitte geben Sie eine gültige E-Mail-Adresse an.';
    }
    if (String(nachricht || '').trim().length < 5) {
      gefunden.nachricht = 'Bitte schreiben Sie Ihre Nachricht (mindestens fünf Zeichen).';
    } else if (String(nachricht).length > NACHRICHT_MAX) {
      gefunden.nachricht = 'Die Nachricht ist zu lang.';
    }
    if (einwilligung_erteilt !== true) {
      gefunden.einwilligung = 'Bitte bestätigen Sie den Hinweis zur Verarbeitung Ihrer Angaben.';
    }
    // F6: Steht die Auswahl im Formular, muss eine der angebotenen Kennungen
    // gewählt sein — sonst ginge ein leerer Wert an den Server.
    if (postfach_sichtbar()) {
      const gewaehlt = String(postfach_gewaehlt || '').trim();
      if (gewaehlt === '' || !postfaecher.some((eintrag) => eintrag.slug === gewaehlt)) {
        gefunden.postfach = postfach_hinweis();
      }
    }
    return gefunden;
  }

  function meldung_aus_antwort(koerper) {
    // Der Server liefert bei Feldpruefungen `message` + `felder`; wir zeigen
    // die Feldmeldungen und sonst eine generische Meldung — nie Interna.
    //
    // F6: `postfach` hat eine EIGENE Meldung — der Servertext nennt die Liste,
    // also ist er der richtige; nur wenn er fehlt, gilt der Feldtext des
    // Bausteins (auch er ist über ein Primo-Feld änderbar).
    const gefunden = {};
    if (koerper && typeof koerper === 'object' && koerper.felder && typeof koerper.felder === 'object') {
      for (const schluessel of Object.keys(koerper.felder)) {
        const text = String(koerper.felder[schluessel] || '').trim();
        if (text === '') continue;
        if (schluessel === 'postfach') {
          gefunden.postfach = postfach_server_hinweis();
        } else if (schluessel === 'name' || schluessel === 'email' || schluessel === 'nachricht' || schluessel === 'einwilligung') {
          gefunden[schluessel] = text;
        }
      }
    }
    return gefunden;
  }

  /**
   * Feldmeldungen einer Fehlerantwort auf die Felder des Formulars abbilden.
   *
   * F6: Das Postfach ist nur DANN ein Feld des Formulars, wenn die Auswahl
   * angezeigt wird und die Liste geladen ist. Ohne Auswahlfeld gibt es für
   * den Besucher nichts zu wählen — dann steht die Postfach-Meldung als
   * allgemeine Meldung da, statt an einem unsichtbaren Feld zu hängen.
   */
  function feldmeldungen_uebernehmen(daten) {
    const gefunden = meldung_aus_antwort(daten);
    if (gefunden.postfach !== undefined && !postfach_sichtbar()) {
      const text = gefunden.postfach;
      delete gefunden.postfach;
      if (Object.keys(gefunden).length === 0) {
        zustand = 'fehler';
        fehlermeldung = text;
        return false;
      }
    }
    fehler = gefunden;
    zustand = 'bereit';
    return true;
  }

  /** True, wenn das Postfach-Auswahlfeld tatsächlich im Formular steht. */
  function postfach_sichtbar() {
    return postfach_auswahl === true && postfaecher.length > 0;
  }

  /** Lokale Feldmeldung für das Postfach (Text über Primo änderbar, F6). */
  function postfach_hinweis() {
    return String(text_postfach_fehler || '').trim() || 'Bitte wählen Sie eines aus der Liste.';
  }

  /** Text einer Postfach-Ablehnung des Servers als Klartext des Bausteins. */
  function postfach_server_hinweis() {
    return String(text_postfach_fehler_server || '').trim() || postfach_hinweis();
  }

  async function absenden(ereignis) {
    if (ereignis && typeof ereignis.preventDefault === 'function') ereignis.preventDefault();
    if (zustand === 'sendet') return;

    fehler = pruefen();
    fehlermeldung = '';
    if (Object.keys(fehler).length > 0) {
      zustand = 'bereit';
      return;
    }

    const adresse = sendeadresse();
    if (adresse === '') {
      zustand = 'fehler';
      fehlermeldung = text_adresse_fehlt;
      return;
    }

    zustand = 'sendet';
    const abbruch = typeof AbortController === 'function' ? new AbortController() : null;
    const wecker = abbruch === null ? null : setTimeout(() => abbruch.abort(), ZEITLIMIT_MS);
    try {
      const koerper = {
        name: String(name).trim(),
        email: String(email).trim(),
        nachricht: String(nachricht).trim(),
        einwilligung: true,
        // Der Honeypot geht mit: ein Mensch laesst ihn leer.
        website: String(honig || ''),
        postfach: String(postfach_gewaehlt || postfach || '').trim()
      };
      const antwort = await fetch(adresse, {
        method: 'POST',
        mode: 'cors',
        credentials: 'omit',
        cache: 'no-store',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify(koerper),
        signal: abbruch === null ? undefined : abbruch.signal
      });

      if (antwort.status === 200) {
        zustand = 'gesendet';
        return;
      }

      let daten = null;
      try {
        daten = await antwort.json();
      } catch (lesefehler) {
        daten = null;
      }
      const feldmeldungen = meldung_aus_antwort(daten);
      if (antwort.status === 400 && Object.keys(feldmeldungen).length > 0) {
        // Gibt es nur die Postfach-Meldung und kein Auswahlfeld, zeigt
        // `feldmeldungen_uebernehmen` sie als allgemeine Meldung an.
        feldmeldungen_uebernehmen(daten);
        return;
      }
      zustand = 'fehler';
      fehlermeldung = antwort.status === 429 ? text_rate_limit : fehlertext;
    } catch (ausnahme) {
      // Netzfehler, Zeitlimit, CORS: derselbe Text. Kein Inhalt in die Konsole.
      zustand = 'fehler';
      fehlermeldung = fehlertext;
    } finally {
      if (wecker !== null) clearTimeout(wecker);
    }
  }

  async function postfaecher_laden() {
    if (postfach_auswahl !== true) return;
    const adresse = listenadresse();
    if (adresse === '') return;
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
      if (!antwort.ok) return;
      const daten = await antwort.json();
      const liste = daten && typeof daten === 'object' && daten.message ? daten.message.postfaecher : null;
      if (!Array.isArray(liste)) return;
      const sauber = [];
      for (const eintrag of liste) {
        if (!eintrag || typeof eintrag !== 'object') continue;
        const slug = String(eintrag.slug || '').trim();
        if (slug === '') continue;
        sauber.push({ slug: slug, bezeichnung: String(eintrag.bezeichnung || slug).trim() });
      }
      postfaecher = sauber;
      // Vorgabe: das im Feld genannte Postfach, sonst das erste der Liste.
      const gewuenscht = String(postfach || '').trim();
      const vorhanden = sauber.some((eintrag) => eintrag.slug === gewuenscht);
      postfach_gewaehlt = vorhanden ? gewuenscht : (sauber.length > 0 ? sauber[0].slug : '');
    } catch (ausnahme) {
      // Ohne Liste bleibt das Formular beim Standardpostfach — kein Fehler.
      postfaecher = [];
    } finally {
      if (wecker !== null) clearTimeout(wecker);
    }
  }

  $effect(() => {
    postfaecher_laden();
  });
</script>

<style>
  /* --dk-* NUR LESEN, nie hier deklarieren (BS-0 F5).

     DUNKELMODUS (Entscheidung Orchestrator 2026-11-04, „Weg 1"): der Baustein
     ERBT von der Site statt eigene Farben zu erzwingen. Ein fester heller
     Text-Fallback (frueher: dunkles Grau) war auf dunklen Primo-Sites unlesbar
     (Kontrast ~1,3:1). Deshalb:
       Text        -> inherit            (Site entscheidet)
       Fläche      -> transparent
       gedämpft    -> color-mix(in srgb, currentColor 70%, transparent)
       Rahmen      -> color-mix(in srgb, currentColor 25%, transparent)
       Akzent      -> NUR Hintergrund/Kontur/Rahmen, nie Textfarbe
       Links/Warn  -> inherit + Unterstreichung bzw. Warn-Rahmen
     color-mix() folgt der geerbten Textfarbe, also in beiden Modi korrekt. */
  .dk-kontakt {
    color: var(--dk-farbe-text, inherit);
    background: var(--dk-farbe-flaeche, transparent);
    font-family: var(--dk-schrift, inherit);
    font-size: var(--dk-groesse-text, 1rem);
    box-sizing: border-box;
    padding: var(--dk-abstand, 0.75rem) 0;
    border-top: var(--dk-rahmen-breite, 1px) solid
      var(--dk-farbe-rahmen, color-mix(in srgb, currentColor 25%, transparent));
  }

  .dk-kontakt *,
  .dk-kontakt *::before,
  .dk-kontakt *::after {
    box-sizing: border-box;
  }

  .dk-kontakt__titel {
    margin: 0 0 var(--dk-abstand, 0.75rem);
    font-family: var(--dk-schrift-ueberschrift, var(--dk-schrift, inherit));
    font-size: var(--dk-groesse-ueberschrift, 1.375rem);
    line-height: 1.25;
    color: var(--dk-farbe-ueberschrift, inherit);
  }

  .dk-kontakt__einleitung {
    margin: 0 0 var(--dk-abstand, 0.75rem);
  }

  .dk-kontakt__formular {
    display: flex;
    flex-direction: column;
    gap: var(--dk-abstand-klein, 0.5rem);
    max-width: 40rem;
  }

  .dk-kontakt__feld {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .dk-kontakt__label {
    font-weight: 600;
    font-size: var(--dk-groesse-klein, 0.875rem);
  }

  .dk-kontakt__eingabe {
    width: 100%;
    font: inherit;
    color: inherit;
    background: var(--dk-farbe-eingabe, transparent);
    border: var(--dk-rahmen-breite, 1px) solid var(--dk-farbe-rahmen, color-mix(in srgb, currentColor 25%, transparent));
    border-radius: var(--dk-rahmen-radius, 0.375rem);
    padding: 0.5rem 0.6rem;
    /* 2.75rem = 44 px: kleinste Fingergroesse (UI-Prinzip K4 „Touch ≥ 44 px").
       2.5rem (40 px) war knapp darunter — gemessen am <select> bei 375 px in
       der Abnahme; Textfelder waren schon >= 44 px. */
    min-height: var(--dk-touch-ziel, 2.75rem);
  }

  /* `select` bringt je nach Browser eine eigene Innenhoehe mit; ohne diese
     Regel blieb er trotz min-height bei 40 px. */
  select.dk-kontakt__eingabe {
    min-height: var(--dk-touch-ziel, 2.75rem);
    height: auto;
  }

  .dk-kontakt__eingabe--mehrzeilig {
    min-height: 8rem;
    resize: vertical;
  }

  .dk-kontakt__eingabe:focus-visible,
  .dk-kontakt__kaestchen:focus-visible,
  .dk-kontakt__knopf:focus-visible {
    outline: 2px solid var(--dk-farbe-akzent, currentColor);
    outline-offset: 2px;
  }

  .dk-kontakt__eingabe[aria-invalid='true'] {
    border-color: var(--dk-farbe-warnung, currentColor);
    border-width: 2px;
  }

  .dk-kontakt__feldhinweis {
    margin: 0;
    font-size: var(--dk-groesse-klein, 0.875rem);
    color: inherit;
  }

  .dk-kontakt__feld--einwilligung {
    flex-direction: row;
    flex-wrap: wrap;
    align-items: flex-start;
    gap: 0.5rem;
  }

  .dk-kontakt__kaestchen {
    width: 1.15rem;
    height: 1.15rem;
    margin-top: 0.15rem;
    flex: 0 0 auto;
  }

  .dk-kontakt__label--kaestchen {
    font-weight: 400;
    flex: 1 1 12rem;
  }

  .dk-kontakt__link {
    /* Akzent nie als Textfarbe (Ä4/Dunkelmodus): Unterstreichung traegt die
       Auszeichnung, die Farbe kommt von der Site. */
    color: inherit;
    text-decoration: underline;
    text-underline-offset: 0.15em;
  }

  .dk-kontakt__absenden {
    margin: 0;
  }

  /* Der Akzent traegt hier die FLAECHE (erlaubt), nicht die Textfarbe. Auf der
     gefuellten Akzentflaeche waere die geerbte Schrift unlesbar, wenn die Site
     hell schreibt. Deshalb Schriftfarbe ueber --dk-farbe-knopf-text (Site kann
     sie setzen); ohne Token bleibt das bisherige Verhalten (weisse Schrift auf
     Akzent) — auf dunklen Sites ist genau das der richtige Kontrast. */
  .dk-kontakt__knopf {
    font: inherit;
    font-weight: 600;
    cursor: pointer;
    color: var(--dk-farbe-knopf-text, #ffffff);
    background: var(--dk-farbe-akzent, #1d4ed8);
    border: var(--dk-rahmen-breite, 1px) solid var(--dk-farbe-akzent, currentColor);
    border-radius: var(--dk-rahmen-radius, 0.375rem);
    padding: 0.6rem 1.2rem;
    min-height: 2.75rem;
  }

  .dk-kontakt__knopf[disabled] {
    cursor: progress;
    opacity: 0.7;
  }

  .dk-kontakt__status {
    margin: 0 0 var(--dk-abstand, 0.75rem);
    padding: var(--dk-abstand-klein, 0.5rem) var(--dk-abstand, 0.75rem);
    border-radius: var(--dk-rahmen-radius, 0.375rem);
    border: var(--dk-rahmen-breite, 1px) solid var(--dk-farbe-rahmen, color-mix(in srgb, currentColor 25%, transparent));
  }

  .dk-kontakt__status--ok {
    border-color: var(--dk-farbe-erfolg, currentColor);
  }

  .dk-kontakt__status--fehler {
    border-color: var(--dk-farbe-warnung, currentColor);
    color: inherit;
  }

  /* Honeypot: nicht sichtbar, aber fuer Screenreader ausgeblendet (aria-hidden) */
  .dk-kontakt__honig {
    position: absolute;
    left: -10000px;
    top: auto;
    width: 1px;
    height: 1px;
    overflow: hidden;
  }

  @media (prefers-reduced-motion: reduce) {
    .dk-kontakt * {
      transition: none !important;
      animation: none !important;
    }
  }
</style>
