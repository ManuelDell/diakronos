# Baustein `kontakt` — Diakronos: Kontaktformular

**Zweck.** Ein Kontaktformular, das die Nachricht als E-Mail über Diakronos an
ein dort hinterlegtes Postfach sendet. **Die Website speichert nichts**, Primo
speichert nichts, Diakronos speichert nichts — die Anfrage geht ausschließlich
als E-Mail hinaus (so ist der Endpunkt `website.kontakt_senden` gebaut).

Postfächer werden in Diakronos unter **Website → Website-Freigaben →
Kontakt-Postfächer** gepflegt (Bezeichnung + Empfängeradresse, dazu der
Schalter „aktiv“). Ohne eingerichtetes Postfach antwortet der Versand mit 503
und das Formular zeigt den Fehlertext.

## Felder

| Feld | Typ | Vorgabe | Bedeutung |
|---|---|---|---|
| Überschrift | Text | „Kontakt“ | leer = keine Überschrift |
| Einleitung | Text | „Schreiben Sie uns …“ | Einleitungssatz über dem Formular |
| Diakronos-Adresse | Text | *gesetzt vom Installer* | Öffentliche Adresse der Installation, absolut (`https://…`) |
| Postfach | Text | leer | Kennung eines Postfachs, z. B. `pfarramt`. Leer = das Standardpostfach aus Diakronos |
| Auswahl anzeigen | Schalter | aus | an = die Auswahlliste der aktiven Postfächer wird geladen und angezeigt |
| Einwilligungstext | Text | neutraler Hinweis | Text neben dem Kästchen; **Pflichtfeld im Formular** (der Absendeknopf bleibt sonst wirkungslos) |
| Adresse der Datenschutzseite | Text | leer | Absolut oder leer; leer = kein Link |
| Beschriftung des Datenschutz-Links | Text | „Datenschutzhinweise“ | |
| Beschriftung des Absendeknopfs | Text | „Nachricht senden“ | |
| Text nach dem Absenden | Text | „Vielen Dank! …“ | Erfolgsmeldung |
| Text bei einem Fehler | Text | „Die Nachricht konnte nicht gesendet werden …“ | Auch bei Netzfefehler, Zeitlimit und fehlender Adresse |

## Datenquelle

* **Senden:** `POST {Diakronos-Adresse}/api/method/website.kontakt_senden`
  mit `{"name", "email", "nachricht", "einwilligung": true, "website": "",
  "postfach": "…"}`. Antwort `200 {"message": {"ok": true}}`; bei Feldfehlern
  `400` mit `felder: {"<feld>": "<Satz>"}` (diese Meldungen zeigt der Baustein
  am jeweiligen Feld), sonst `403`/`429`/`503` mit generischer Meldung.
* **Postfach-Auswahl:** `GET {Diakronos-Adresse}/website/oeffentlich/postfaecher`
  → `{"message": {"postfaecher": [{"slug", "bezeichnung"}, …]}}` — nur aktive
  Postfächer, **ohne E-Mail-Adressen**.

## Verhalten und Datenschutz

* **Honeypot:** Das Feld `website` ist für Menschen unsichtbar
  (`position: absolute; left: -10000px`, `aria-hidden`, `tabindex="-1"`). Ist
  es gefüllt, antwortet der Server mit „ok“, versendet aber nichts. Der
  Baustein prüft den Honeypot NICHT selbst — das entscheidet ausschließlich der
  Server, damit die Umgehung nicht im Client liegt.
* **Client-Validierung wie der Server:** Pflichtfelder, Längen (Name 120,
  Adresse 200, Nachricht 5000 Zeichen), eine Adresse mit genau einem `@` und
  einer Domain, Einwilligung. Der Server prüft dasselbe noch einmal; seine
  Feldmeldungen haben Vorrang und werden am Feld angezeigt.
* **Zustände:** sendet (Knopf gesperrt und „Wird gesendet …“), gesendet
  (`role="status"`), Fehler (`role="alert"`). Feldmeldungen sind über
  `aria-describedby` an das Feld gebunden, fehlerhafte Felder tragen
  `aria-invalid="true"`.
* **Zeitlimit 15 s** je Anfrage; danach zeigt der Block den Fehlertext.
* **Kein Inhalt in der Konsole**, kein `console.log` von Eingaben.
* Nach dem Absenden bleiben die Eingaben im Formular stehen, bis die
  Erfolgsmeldung an die Stelle des Formulars tritt — wer zurück will, lädt die
  Seite neu (bewusst kein „Nochmal senden“-Knopf: sonst ginge dieselbe
  Nachricht zweimal hinaus).
* Gestaltung über `--dk-*` (nur gelesen): zusätzlich zu den Tokens der
  Terminliste `--dk-farbe-eingabe`, `--dk-farbe-knopf-text`,
  `--dk-farbe-erfolg`.
