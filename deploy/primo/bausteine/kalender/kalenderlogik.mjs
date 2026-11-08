/**
 * Kalender-Hilfslogik des Bausteins „Diakronos: Kalender" (BS-2b).
 *
 * WARUM EIGENE DATEI
 * ==================
 * Primo kopiert einen Bibliotheksblock beim Einsetzen in eine Site; die Kopie
 * lebt danach für sich (README Regel 1). Für den AUSGELIEFERTEN Block steht
 * diese Logik deshalb zusätzlich im `<script>` von `component.svelte` — die
 * Datei hier ist die Fassung, die `node --test` direkt prüfen kann, und die
 * Quelle, aus der der Blockteil erzeugt wurde (gleiche Funktionen, gleiche
 * Namen; ein Wächtertest vergleicht die öffentlichen Funktionsnamen).
 *
 * Zeitrechnung
 * ============
 * Alle Tagesangaben rechnen in der Zeitzone der Gemeinde (`ZEITZONE`), nicht
 * in der des Browsers. Der Monat ist ein „naiver" Kalendermonat (Jahr + Monat)
 * — kein `Date`-Objekt, damit ein Monatswechsel keine Zeitzonenfalle ist
 * (Ende Oktober: MEZ/MESZ-Wechsel, 25-Stunden-Tag).
 */

/** Zeitzone, in der Termine angezeigt und Monatsraster gerechnet werden. */
export const ZEITZONE = 'Europe/Berlin';

/** Monatsnamen für die Überschrift (Index 0 = Januar). */
const MONATSNAMEN = [
  'Januar', 'Februar', 'März', 'April', 'Mai', 'Juni',
  'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember'
];

/** Wochentagskürzel, Index wie `Date#getUTCDay()` (0 = Sonntag). */
const WOCHENTAGE_KURZ = ['So', 'Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa'];
/** Wochentagsnamen (lang), gleicher Index. */
const WOCHENTAGE_LANG = [
  'Sonntag', 'Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag'
];

/** Zahl aus einem Feldwert; unbrauchbar -> Vorgabe (ganzzahlig, begrenzt). */
export function zahl(wert, vorgabe, minimum, maximum) {
  const geprueft = Number(String(wert === null || wert === undefined ? '' : wert).replace(',', '.'));
  if (!Number.isFinite(geprueft)) return vorgabe;
  return Math.min(maximum, Math.max(minimum, Math.trunc(geprueft)));
}

/** Kennungen aus einem Textfeld: "a, b" oder "a" (leer -> leere Liste). */
export function kennungen(wert) {
  return String(wert || '')
    .split(',')
    .map((teil) => teil.trim())
    .filter((teil) => teil !== '');
}

/** Nur absolute http(s)-Adressen; sonst "" (kein `javascript:` usw.). */
export function nur_webadresse(wert) {
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

/** ISO-Zeitpunkt -> Date; ungueltig -> null. */
export function als_datum(wert) {
  const text = String(wert || '').trim();
  if (text === '') return null;
  const datum = new Date(text);
  return Number.isNaN(datum.getTime()) ? null : datum;
}

/** Teile eines Zeitpunkts in der Zeitzone der Gemeinde (de-DE, 2-stellig). */
export function teile(datum) {
  const stuecke = new Intl.DateTimeFormat('de-DE', {
    timeZone: ZEITZONE,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit'
  }).formatToParts(datum);
  const wert = (art) => (stuecke.find((s) => s.type === art) || {}).value || '';
  return { tag: wert('day'), monat: wert('month'), jahr: wert('year') };
}

/** „2026-10-25" eines Zeitpunkts in der Zeitzone der Gemeinde. */
export function isodatum(datum) {
  const { tag, monat, jahr } = teile(datum);
  return jahr + '-' + monat + '-' + tag;
}

/** 0..6 mit 0 = Sonntag, wie `Date#getUTCDay()`. */
function wochentag_nummer(jahr, monat, tag) {
  return new Date(Date.UTC(jahr, monat - 1, tag)).getUTCDay();
}

/**
 * „2026-10-31“ — letzter Tag des Monats (einschliesslich).
 *
 * Ein Monat ist das Fenster, das der Baustein monatsweise abfragt: die API
 * bekommt `von`/`bis` auf volle Monate, nicht auf das Raster (sonst ladt ein
 * Blaettern ueber die Monatsgrenze Termine doppelt bzw. gar nicht).
 */
export function zeitraum_ein_monat(jahr, monat) {
  const monatstext = String(monat).padStart(2, '0');
  return {
    von: [String(jahr).padStart(4, '0'), monatstext, '01'].join('-'),
    bis: [String(jahr).padStart(4, '0'), monatstext, String(tage_im_monat(jahr, monat)).padStart(2, '0')].join('-')
  };
}

/**
 * Rastertage in Wochen geteilt: `[{ schluessel, tage }]`, je sieben Tage.
 *
 * Ein <table> verlangt <tr> zwischen <tbody> und <td>; die Vorlage iteriert
 * deshalb ueber Wochen und darin ueber Tage (Review-Befund 08.11.).
 */
export function raster_wochen(tage) {
  const liste = Array.isArray(tage) ? tage : [];
  const wochen = [];
  for (let i = 0; i < liste.length; i += 7) {
    const woche = liste.slice(i, i + 7);
    if (woche.length === 0) continue;
    wochen.push({ schluessel: (woche[0] && woche[0].iso) || String(i), tage: woche });
  }
  return wochen;
}

/**
 * Termine einer Zelle: hoechstens `max` Termine, der Rest als Zahl.
 * Rueckgabe `{ termine, weitere }` — die Zelle zeigt „+n weitere“ statt sich
 * zu ueberlaufen.
 */
export function zelle_aufteilen(termine, max = 3) {
  const liste = Array.isArray(termine) ? termine : [];
  const grenze = Math.max(1, Math.trunc(max) || 3);
  if (liste.length <= grenze) return { termine: liste, weitere: 0 };
  return { termine: liste.slice(0, grenze), weitere: liste.length - grenze };
}

/**
 * Die Anzeige-Antwort des juengsten Abrufs: bei schnellem Blaettern trifft
 * eine alte Antwort spaeter ein — `abruf_ist_aktuell(meine, aktuell)` sagt,
 * ob sie noch gilt.
 */
export function abruf_ist_aktuell(meine, aktuell) {
  return Number(meine) === Number(aktuell);
}

/**
 * Anmeldeadresse eines Termins: absolute Adresse bleibt; ein relativer Pfad
 * bekommt die Diakronos-Basis davor (Praefix nur EINMAL — wie in
 * `anmeldung/component.svelte`).
 */
export function anmelde_adresse(wert, basisadresse) {
  const text = String(wert || '').trim();
  if (text === '') return '';
  if (/^https?:\/\//i.test(text)) return nur_webadresse(text);
  const basiswert = nur_webadresse(basisadresse);
  if (basiswert === '' || !text.startsWith('/')) return '';
  try {
    const ziel = new URL(text, basiswert + '/');
    const basis_teile = new URL(basiswert);
    const basis_pfad = basis_teile.pathname.replace(/\/+$/, '');
    if (basis_pfad !== '' && ziel.pathname.startsWith(basis_pfad + '/')) {
      const rest = ziel.pathname.slice(basis_pfad.length);
      return basiswert + rest + ziel.search;
    }
    return basis_teile.origin + ziel.pathname + ziel.search;
  } catch (fehler) {
    return '';
  }
}

/**
 * Tage eines Monats (Monat 1..12). Schaltjahre nach Gregorianischer Regel.
 * Naiv gerechnet (UTC-Mitternacht), damit keine Zeitzone hineinspielt.
 */
export function tage_im_monat(jahr, monat) {
  return new Date(Date.UTC(jahr, monat, 0)).getUTCDate();
}

/** Monat um `schritt` verschieben (-1 zurück, +1 vor); Jahr läuft mit. */
export function monat_verschieben(jahr, monat, schritt) {
  const gesamt = jahr * 12 + (monat - 1) + Math.trunc(schritt);
  return { jahr: Math.floor(gesamt / 12), monat: (gesamt % 12 + 12) % 12 + 1 };
}

/**
 * Ein Schritt der Steuerung: gibt den Monat NACH dem Schritt aus — die Form,
 * die der Baustein in seinem `schritt()` braucht (Jahr und Monat laufen mit).
 */
export function schritt(jahr, monat, richtung) {
  return monat_verschieben(jahr, monat, richtung);
}

/** „2026-10" — erster Tag des Monats. */
export function monat_start(jahr, monat) {
  return [String(jahr).padStart(4, '0'), String(monat).padStart(2, '0'), '01'].join('-');
}

/** „2026-10-31" — letzter Tag des Monats (einschließlich). */
export function monat_ende(jahr, monat) {
  return monat_start(jahr, monat).slice(0, 8) + String(tage_im_monat(jahr, monat)).padStart(2, '0');
}

/** Überschrift eines Monats: „Oktober 2026". */
export function monat_titel(jahr, monat) {
  return MONATSNAMEN[monat - 1] + ' ' + jahr;
}

/**
 * Wochenstart als Zahl (1 = Montag, 0 = Sonntag).
 * Alles außer „sonntag" gilt als Montag — der deutsche Standard.
 */
export function wochenstart_nummer(wert) {
  return String(wert || '').trim().toLowerCase() === 'sonntag' ? 0 : 1;
}

/** Montag der Woche, in der `datum` liegt (als Date, UTC-Mitternacht). */
export function wochenstart_von(datum, wochenstart = 1) {
  const start = wochenstart_nummer(wochenstart);
  const kopie = new Date(Date.UTC(datum.getUTCFullYear(), datum.getUTCMonth(), datum.getUTCDate()));
  const abstand = (kopie.getUTCDay() - start + 7) % 7;
  kopie.setUTCDate(kopie.getUTCDate() - abstand);
  return kopie;
}

/**
 * Monatsraster: die Tage, die im Monat `monat` angezeigt werden.
 *
 * Das Raster beginnt am Wochenstart VOR oder AM 1. des Monats und endet am
 * Wochenende NACH oder AM dem letzten Tag — volle Wochen, keine Lücken.
 * Rückgabe: `[{ jahr, monat, tag, iso, im_monat, wochentag, heute }]`.
 * `heute` markiert den heutigen Tag (nur, wenn er im Raster liegt und im
 * gezeigten Monat ist).
 */
export function monatsraster(jahr, monat, wochenstart = 1, heute_iso = '') {
  const erster = new Date(Date.UTC(jahr, monat - 1, 1));
  const letzter = new Date(Date.UTC(jahr, monat - 1, tage_im_monat(jahr, monat)));
  const von = wochenstart_von(erster, wochenstart);
  const bis = wochenstart_von(letzter, wochenstart);
  bis.setUTCDate(bis.getUTCDate() + 6);
  const tage = [];
  for (let zeit = von.getTime(); zeit <= bis.getTime(); zeit += 24 * 60 * 60 * 1000) {
    const tag = new Date(zeit);
    const j = tag.getUTCFullYear();
    const m = tag.getUTCMonth() + 1;
    const t = tag.getUTCDate();
    const iso = [String(j).padStart(4, '0'), String(m).padStart(2, '0'), String(t).padStart(2, '0')].join('-');
    tage.push({
      jahr: j,
      monat: m,
      tag: t,
      iso,
      im_monat: j === jahr && m === monat,
      wochentag: tag.getUTCDay(),
      heute: iso === heute_iso
    });
  }
  return tage;
}

/**
 * Kopfzeile des Rasters: Wochentagskürzel ab dem Wochenstart.
 * Bei Montag-Start: Mo Di Mi Do Fr Sa So.
 */
export function raster_kopf(wochenstart = 1) {
  const start = wochenstart_nummer(wochenstart);
  return Array.from({ length: 7 }, (_, i) => WOCHENTAGE_KURZ[(start + i) % 7]);
}

/** „Sa., 08.11." eines ISO-Datums (Tagesanteil, ohne Zeitzone). */
export function tagestext(iso) {
  const treffer = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(iso || '').trim());
  if (!treffer) return '';
  const jahr = Number(treffer[1]);
  const monat = Number(treffer[2]);
  const tag = Number(treffer[3]);
  const nummer = wochentag_nummer(jahr, monat, tag);
  return WOCHENTAGE_KURZ[nummer] + '., ' + String(tag).padStart(2, '0') + '.' + String(monat).padStart(2, '0') + '.';
}

/** „Samstag, 8. November 2026" eines ISO-Datums. */
export function tagestext_lang(iso) {
  const treffer = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(iso || '').trim());
  if (!treffer) return '';
  const jahr = Number(treffer[1]);
  const monat = Number(treffer[2]);
  const tag = Number(treffer[3]);
  const nummer = wochentag_nummer(jahr, monat, tag);
  return WOCHENTAGE_LANG[nummer] + ', ' + tag + '. ' + MONATSNAMEN[monat - 1] + ' ' + jahr;
}

/** „10:00" in der Zeitzone der Gemeinde (24-Stunden-Form). */
export function uhrzeittext(datum) {
  const stuecke = new Intl.DateTimeFormat('de-DE', {
    timeZone: ZEITZONE,
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23'
  }).formatToParts(datum);
  const wert = (art) => (stuecke.find((s) => s.type === art) || {}).value || '';
  return wert('hour') + ':' + wert('minute');
}

/** „10:00 – 11:30" am selben Tag; sonst nur der Beginn. */
export function zeitfenster(beginn, ende) {
  const start = als_datum(beginn);
  if (start === null) return '';
  const ende_datum = als_datum(ende);
  if (ende_datum === null) return uhrzeittext(start);
  if (isodatum(start) !== isodatum(ende_datum)) return uhrzeittext(start);
  return uhrzeittext(start) + ' – ' + uhrzeittext(ende_datum);
}

/**
 * Zeitangabe eines Termins für die Anzeige.
 * Ganztägig -> `text_ganztaegig` (nie „00:00"), sonst das Zeitfenster.
 */
export function zeitangabe(eintrag, text_ganztaegig = 'ganztägig') {
  if (!eintrag || typeof eintrag !== 'object') return '';
  if (eintrag.ganztaegig === true) return String(text_ganztaegig || '');
  return zeitfenster(eintrag.beginn, eintrag.ende);
}

/**
 * Ende eines mehrtägigen Termins: „So., 09.11." — sonst „".
 *
 * F1: Ein mehrtägiger/ganztägiger Termin braucht seinen Zeitraum, sonst
 * liest er sich wie ein eintägiger. Das Ende kommt UNVERÄNDERT aus der
 * Antwort: Diakronos speichert das Ganztags-Ende EINSCHLIESSLICH und die
 * Lese-API gibt es so aus (`ende` = letzter Tag) — es wird KEIN Tag
 * abgezogen. Liegt das Ende am selben Kalendertag wie der Beginn
 * (eintägig, oder ein Termin bis 23:59 desselben Tages), bleibt das Feld
 * leer.
 */
export function ende_text(beginn, ende) {
  const start = als_datum(beginn);
  const ende_datum = als_datum(ende);
  if (ende_datum === null) return '';
  if (start !== null && isodatum(start) === isodatum(ende_datum)) return '';
  return tagestext(isodatum(ende_datum));
}

/**
 * Termine je Kalendertag (Schlüssel „JJJJ-MM-TT" in der Zeitzone der Gemeinde).
 * Die Reihenfolge innerhalb eines Tages bleibt die der Antwort (nach Beginn).
 */
export function termine_je_tag(termine) {
  const karte = new Map();
  for (const eintrag of Array.isArray(termine) ? termine : []) {
    if (!eintrag || typeof eintrag !== 'object') continue;
    const beginn = als_datum(eintrag.beginn);
    if (beginn === null) continue;
    const schluessel = isodatum(beginn);
    if (!karte.has(schluessel)) karte.set(schluessel, []);
    karte.get(schluessel).push(eintrag);
  }
  return karte;
}

/**
 * Farbe eines Termins als CSS-Wert — NUR wenn sie wie eine HTML-Farbe aussieht
 * (Hex oder `rgb()/rgba()/hsl()`), sonst "". Ein Kalenderfeld ist Freitext;
 * ein Wert wie `url(…)` oder `expression(…)` darf nie ins CSS gelangen.
 */
export function farbe_wert(wert) {
  const text = String(wert || '').trim();
  if (/^#[0-9a-f]{3,8}$/i.test(text)) return text;
  if (/^(rgb|rgba|hsl|hsla)\(\s*[0-9%,.\s/]+\)$/i.test(text)) return text;
  return '';
}

/** Prüfsummenfreier Vergleich: zwei ISO-Daten liegen im selben Monat. */
export function im_monat(iso, jahr, monat) {
  return String(iso || '').startsWith(monat_start(jahr, monat).slice(0, 7));
}

export default {
  ZEITZONE,
  zahl,
  kennungen,
  nur_webadresse,
  als_datum,
  teile,
  isodatum,
  ende_text,
  tage_im_monat,
  monat_verschieben,
  schritt,
  monat_start,
  monat_ende,
  monat_titel,
  wochenstart_nummer,
  wochenstart_von,
  monatsraster,
  raster_kopf,
  tagestext,
  tagestext_lang,
  ende_text,
  uhrzeittext,
  zeitfenster,
  zeitangabe,
  termine_je_tag,
  farbe_wert,
  im_monat,
  zeitraum_ein_monat,
  raster_wochen,
  zelle_aufteilen,
  abruf_ist_aktuell,
  anmelde_adresse
};
