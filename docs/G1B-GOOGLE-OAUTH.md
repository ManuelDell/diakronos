# Google-Anmeldung und Kalenderimport im Backend (G1b)

Aufbauend auf G1a ergänzt dieses Paket das Backend — ohne Frappe, ohne Desk und
ohne Änderungen am Quellcode der Oberfläche. Die Importseite selbst ist Teil von
[G2](G2-KALENDER-IMPORT.md). Es gibt **keine** bidirektionale Synchronisierung:
der Import liest bei Google und schreibt in den lokalen Kalender.

## Schnittstellen für die Oberfläche

Präfix: `/api/method/diakronos.kronos.api.google_import.`
Antworten liegen wie bisher in `message`.

- `get_oauth_url` (GET): `{url, redirect_uri}`. Die Google-Adresse im Browser
  öffnen.
- `exchange_code` (POST): `{code, state}` → `{success: true}`. Normalerweise
  übernimmt der Callback den Austausch; die Seite muss ihn nicht wiederholen.
- `get_google_calendars` (GET): Liste mit `id`, `summary`, `backgroundColor`,
  `primary`. Alle Seiten werden gelesen.
- `start_import` (POST): `mappings_json` ist eine JSON-kodierte Liste. Antwort
  `{queued: true}` bedeutet nur eingereiht, nicht bereits importiert.
  Pro Eintrag: `google_id`, `google_name`, `create_new` (echtes JSON-Boolean),
  `target_kalender`, `color` (`#RRGGBB`), `time_filter` (`all`, `from_today`,
  `last_year`, `last_3_years`). Bestehende Ziele müssen existieren.
- Aus G1a unverändert: `get_credentials_status`, `save_credentials`,
  `upload_ical`.

**Callback:** `GET /google-calendar-callback?code=...&state=...`.
Nur eine berechtigte, gültige Sitzung kann den Code austauschen. Erfolg:
HTTP 303 auf `/diakonos?gcal_step=2#/kalender/import`; Fehler:
`/diakonos?gcal_error=<URL-kodierte allgemeine Meldung>#/kalender/import`.
Die Parameter stehen absichtlich vor dem Fragment, damit die Seite sie lesen
und anschließend bereinigen kann. Antworten sind `no-store` und `no-referrer`;
die Zugriffsprotokolle des Servers entfernen OAuth-Parameter. Ein
vorgeschalteter Proxy muss diese Parameter ebenfalls aus seinen
Zugriffsprotokollen ausschließen.

**Fortschritt:** Socket.IO auf demselben Ursprung, Sitzungscookie wird
automatisch mitgesendet. Ereignis `gcal_import_progress`: `starting`,
`importing`, ggf. `warning`/`error`, abschließend `done` mit
`total_imported`, `total_skipped`, `calendars` und ggf. `error`. Der Fortschritt
geht nur an `user:<angemeldeter Benutzer>`; Gäste und frei behauptete
Identitäten werden nicht akzeptiert. Die Seite verbindet vor dem Start und
entfernt den Empfänger beim Verlassen.

## Sicherheits- und Datenvertrag

- Nur `Administrator`, `System Manager`, `Mitgliederadministrator`,
  `Kalenderadministrator`; alle vier neuen Endpunkte sind für Gäste gesperrt.
  Der Hintergrund-Worker prüft nach der Wartezeit Identität und Rollen erneut.
- State: 32 zufällige Bytes, 600 Sekunden in Redis, gebunden an Benutzer,
  konkrete Sitzung und aktuelle Zugangsdaten/Redirect-URI. Redis `GETDEL`
  verbraucht ihn atomar; fremde, abgelaufene und wiederverwendete States werden
  abgelehnt. Ein Redis-Ausfall ist kein erfolgreicher Ablauf.
- Client-Secret und Tokens verwenden ausschließlich die Fernet-Helfer aus G1a.
  `SECRET_KEY` muss stabil und gesichert sein. Status, Fehler und Aufträge
  enthalten keine Geheimnisse, Codes oder Google-Antwortkörper. Ein gemeinsamer
  Google-Zugang für die ganze Installation, keine Mehrbenutzer-Tokenablage.
- Token-Neubezug bei Ablauf mit 60 Sekunden Reserve; das Refresh-Token bleibt
  erhalten, wenn Google kein neues liefert. Die Einstellungen werden unter
  Zeilensperre aktualisiert, damit Neubezug und Wechsel sich nicht gegenseitig
  überschreiben. 401/403/429 werden allgemein gemeldet; kein unbeschränktes
  Wiederholen bei Quotenfehlern.
- Die Auftragswarteschlange ist bewusst die Standardliste `default`, weil der
  Worker im Compose-Verbund genau diese liest. Zeitlimit 600 Sekunden.
- Redis-Pub/Sub verbindet getrennte Worker mit dem Socket.IO-Server der
  Anwendung. Jeder Anwendungs-Lebenszyklus erhält einen eigenen Empfänger;
  Tests teilen keine Empfänger aus bereits geschlossenen Schleifen.
- Seitenweise Abfrage mit begrenzter Anzahl und Ablehnung wiederholter
  Seitenmarken. Maximal 100 Kalenderzuordnungen pro Auftrag, 10.000 Ereignisse
  je Kalender. Serien werden von Google expandiert (`singleEvents=true`);
  abgesagte und ungültige Ereignisse werden übersprungen. Fortschritt je Seite,
  nicht je Termin.
- Transaktion je Kalender: Scheitert eine Seite, wird dieser Kalender samt
  neuen Ereignissen zurückgerollt; zuvor erfolgreich importierte Kalender
  bleiben erhalten. Ein Fehler in `done` verhindert eine falsche
  Erfolgsmeldung.
- Duplikate im Zielkalender werden über stabile `gcal:`-Hashes der Ereignis-ID
  erkannt. Google-IDs werden im Pfad vollständig URL-kodiert.
- Zeitvertrag aus G1a: zeitzonenbehaftete Zeitpunkte nach `CALENDAR_TIMEZONE`
  (Vorgabe `Europe/Berlin`) umrechnen und kalenderlokal ohne Offset speichern.
  Ganztägige Einträge behalten den exklusiven Endtag.

## Google Cloud Console – der manuelle echte Rundlauf

1. In der Google Cloud Console ein Projekt wählen oder anlegen und die
   „Google Calendar API“ aktivieren.
2. OAuth-Zustimmungsbildschirm konfigurieren. Bei externer App im Testmodus
   das verwendete Google-Konto als Testnutzer eintragen. Nur den Bereich
   `https://www.googleapis.com/auth/calendar.readonly` anfordern.
3. OAuth-Client vom Typ „Webanwendung“ anlegen. Als autorisierte Redirect-URI
   exakt `https://<öffentlicher-app-host>/google-calendar-callback` eintragen:
   Protokoll, Host, Port und Pfad müssen mit den gespeicherten Einstellungen
   übereinstimmen, ohne Parameter und ohne Fragment.
4. Google lässt als Web-Redirect keine rohe LAN-Adresse zu und verlangt HTTPS
   (Ausnahme: localhost/Loopback). Für einen echten Ablauf einen erreichbaren
   HTTPS-Namen verwenden; `http://localhost:<port>/google-calendar-callback`
   nur für erlaubte lokale Tests mit passender Weiterleitung. Die aus dem Host
   abgeleitete Adresse ist eine Vorgabe, keine Zusicherung, dass Google sie
   zulässt. Hinter einem Proxy die öffentliche Adresse ausdrücklich speichern,
   nicht einen internen Containernamen.
5. Mit einer Sitzung als Import-Administrator Client-ID und Secret über die
   Importseite speichern. Das Secret nie in Protokolle oder Adressen einfügen.
   Im selben Browserprofil autorisieren und innerhalb von zehn Minuten
   zurückkehren. Erfolg muss auf `#/kalender/import` führen.
6. Einen kleinen Testkalender wählen, den Import starten und den Fortschritt
   bis `done` prüfen. Uhrzeit und Ganztag kontrollieren; ein erneuter Import in
   dasselbe Ziel muss Duplikate überspringen. Im echten Konto nichts
   automatisch löschen.

Der echte Google-Rundlauf ist **ungetestet** und braucht die Zugangsdaten des
Betreibers. Alle automatisierten Tests verwenden ausschließlich simulierte
Google-Antworten. Google-Referenz:
[OAuth Web Server – Redirect URI validation](https://developers.google.com/identity/protocols/oauth2/web-server#uri-validation).

## Verifikation

Gemessen gegen eine Wegwerf-Datenbank mit privater Redis-Instanz und ohne
Berührung der Betriebsdaten:

- Google-Tests (G1a/G1b ohne Socket.IO): 119 bestanden.
- Socket.IO/Auftragswarteschlange gezielt: 10 bestanden, inklusive zweier
  unabhängiger Server-Lebenszyklen und Zustellung aus einem getrennten Prozess.
- Echte HTTP-Prüfung: sieben Originalpfade für Gäste gesperrt (403), Callback
  303, Wiederverwendung eines States abgelehnt, Kalenderliste mit Seiten 200.
- Echte Kette aus Auftragswarteschlange und Socket.IO: 2 Ereignisse importiert,
  1 abgesagt; erneuter Import 0 importiert / 3 übersprungen; UTC 09:00 → 11:00
  in der Kalenderanzeige.
- Vollständige Python-Suite im gebauten Image ohne Ausschlüsse: 2051 bestanden,
  20 übersprungen, Exit 0.
- Migration: `alembic upgrade head` und `alembic check` ohne neue Operationen.

**Kein Bestandteil dieser Abnahme** ist ein Aufruf gegen einen laufenden
Betriebsstack: dort waren die G1a-Endpunkte vor dem Ausrollen für Gäste mit 403
und die neuen G1b-Endpunkte mit 404 beantwortet. Nach dem Ausrollen sind beide
zusammen zu prüfen (siehe [ENTWICKLER-README](ENTWICKLER-README.md), Abschnitt 4).
