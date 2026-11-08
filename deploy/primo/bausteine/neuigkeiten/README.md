# Neuigkeiten (`neuigkeiten`)

Zeigt veröffentlichte Beiträge aus Diakronos als Liste oder Karten.
„Weiterlesen" klappt den Beitragsinhalt direkt im Baustein auf.

## Felder

| Feld | Bedeutung |
|---|---|
| Überschrift | Titel über der Liste |
| Diakronos-Adresse | Absolute Adresse der Diakronos-Installation |
| Darstellung | `karten` oder `liste` |
| Anzahl der Beiträge | 1–50 |
| Kategorie | Kategoriename des Beitrags, leer = alle |
| Bilder anzeigen | aus = Bilder werden nicht einmal geladen |
| „Weiterlesen" anbieten | aus = es wird nur der Auszug gezeigt |
| Beschriftungen | „Weiterlesen", „Zuklappen" |
| Texte | Laden, Leertext, Fehlertext |

## Datenquelle

`GET {Diakronos-Adresse}/website/oeffentlich/beitraege?limit=…&kategorie=…`

Nur Beiträge mit `veroeffentlicht = true`, `auf_website = true`, nicht im
Papierkorb. Felder: `id, titel, datum, kategorie, auszug, inhalt, bild_url`.
**Kein** Autor, keine Adresse, kein interner Name.

## Sicherheit des Inhalts (zwei Stufen)

1. **Server:** `inhalt` ist bereits bereinigtes HTML aus einer Allowlist
   (`p, br, strong, em, ul, ol, li, a[href http|https|mailto], h2, h3,
   blockquote`; nur `href` an `a`; fremde Schemata verlieren das `href`).
2. **Browser:** Der Baustein steckt das **nicht** ungefiltert in
   `{@html}`. Er parst es mit `DOMParser` (inert — Skripte laufen dort nicht)
   und baut die Knoten einzeln neu auf: nur erlaubte Elemente, alle Texte und
   Attribute maskiert, `href` erneut gegen die Schema-Liste geprüft. Erst
   dieser Neubau geht in `{@html}`.

Damit kann auch ein Fehler in der Server-Bereinigung keinen Skript- oder
Attribut-Code auf die Website bringen.

## Aufklappen

Der „Weiterlesen"-Knopf ist ein echter `<button>` mit `aria-expanded` und
`aria-controls` (Tastatur, Fokus, Screenreader). Nur Beiträge mit Inhalt sind
aufklappbar; ohne Inhalt entfällt der Knopf. Das Zuklappen stellt den Auszug
wieder her.
