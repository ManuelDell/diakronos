# Google-Import: Zugangsdaten und iCal (G1a)

## Schnittstelle

Alle drei Endpunkte sind unter dem Originalpfad
`/api/method/diakronos.kronos.api.google_import.<funktion>` registriert:

- `get_credentials_status`: GET, nur `configured`, `authorized`, `redirect_uri`.
- `save_credentials`: POST mit `client_id`, `client_secret`, optional `redirect_uri`.
  Standard-Redirect ist die Anfrage-Basis plus `/google-calendar-callback`.
  Ein Wechsel der Zugangsdaten setzt Autorisierung und Tokens zurück.
- `upload_ical`: POST mit Base64-String `file_content_b64`, optional
  `create_new`, `target_kalender`, `calendar_name_new`, `color`.
  Rückgabe: `success`, `imported`, `skipped`, `kalender`.

Erlaubt sind der Benutzer Administrator sowie die Rollen System Manager,
Mitgliederadministrator und Kalenderadministrator. Gäste und andere Benutzer
werden serverseitig abgewiesen.

## Sicherheit und Datenspeicherung

- `client_secret` und `token_data` sind versionierte Fernet-Ciphertexte.
  Schlüsselableitung: SHA-256 aus domänenspezifischem Präfix und `SECRET_KEY`.
  Der unsichere Entwicklungs-Vorgabewert wird zum Speichern abgelehnt.
- `SECRET_KEY` muss stabil bleiben und zusammen mit der Datenbank gesichert
  werden. Ein anderer Schlüssel entschlüsselt bestehende Zugangsdaten nicht. Es
  gibt keinen Klartext-Rückfallweg und keine Geheimnisse in Status- oder
  Fehlerantworten.
- Die Migration `g1a_google_secrets` verbreitert `client_secret` zu Text und
  verschlüsselt vorhandene Klartext-Zugangsdaten und -Tokens. Kein neuer
  Datentyp ohne Anpassung des Generators: `tools/gen_models.py` erzeugt das
  Modell.
- Der Rückweg der Migration löscht die Zugangsdaten und die Autorisierung,
  statt Klartext herzustellen. Danach ist eine erneute Konfiguration und
  Google-Autorisierung nötig.
- Die generische CRUD-API und der Frappe-Desk-Schreibweg sind für die
  Google-Einstellungen auch für Administratoren gesperrt. Dadurch lässt sich die
  Verschlüsselung nicht über einen zweiten Schreibweg umgehen.

## iCal-Verhalten und Grenzen

RFC 5545 wird mit `icalendar` gelesen; UTF-8, Faltungszeilen, Text-Escapes,
DURATION, DATE, UTC und TZID werden berücksichtigt. Zeitzonenbehaftete Termine
werden in die Kalenderzone umgerechnet und **offsetlos lokal** gespeichert.
`CALENDAR_TIMEZONE` ist ein geprüfter IANA-Zonenname, Vorgabe `Europe/Berlin`,
unabhängig von der Zeitzone des Containers. Fließende Zeiten und reine Datumsangaben
bleiben unverändert; ganztägige Enddaten bleiben exklusiv. Ohne DTEND/DURATION
ist ein ganztägiger Termin einen Tag lang.

Das entspricht dem bestehenden Vertrag: die Anwendung speichert lokale
Uhrzeiten, liefert offsetlose Zeichenketten, und die Oberfläche zeigt sie als
lokale Browserzeit. Die Kalenderzone muss daher zur Nutzungszone passen; eine
Anzeige desselben Zeitpunkts in beliebigen Browser-Zeitzonen ist nicht Teil
dieses Vertrags. Bestehende manuell angelegte Werte werden nicht verändert.
Berlin 05.10.2026 18:00 bleibt 18:00; UTC 16:00 ergibt lokal dieselben 18:00.
Wiederholungsregeln werden zuerst in ihrer Quellzone aufgelöst, anschließend
wird jedes Vorkommen umgerechnet: eine Berliner Serie bleibt beim Herbstwechsel
bei 18:00, eine UTC-Serie um 16:00 erscheint vorher um 18:00 und danach um 17:00.

Begrenzte Serien (DAILY/WEEKLY/MONTHLY/YEARLY mit COUNT oder UNTIL) werden als
einzelne Termine materialisiert; Ausnahmedaten (EXDATE) werden berücksichtigt.
Maximal 10.000 Vorkommen pro Datei und Serie, UNTIL höchstens 100 Jahre nach
Beginn. Nicht positive Abstände werden abgelehnt. Offene Serien ohne
COUNT/UNTIL, RDATE, EXRULE und Ausnahmen über RECURRENCE-ID werden ausdrücklich
abgewiesen — nicht still gekürzt und nicht falsch importiert. Für solche
Exporte ist ein begrenzter oder aufgelöster Export nötig.

Der Dateityp wird am VCALENDAR-Inhalt geprüft (der Vertrag enthält keinen
Dateinamen und keinen MIME-Parameter). Base64 und UTF-8 werden streng geprüft,
die Größe gegen `MAX_UPLOAD_BYTES`. Ungültige Dateien schreiben nichts. Der
gesamte Import einschließlich Kalender und Leserechten ist eine Transaktion.

Duplikate werden anhand kalenderbezogener stabiler Hashes aus UID und Vorkommen
übersprungen. Derselbe Quellkalender kann somit in zwei verschiedene lokale
Kalender importiert werden. Neue Kalender bekommen die Leserechte
Administrator/Kalenderadministrator; Namenskollisionen erhalten einen Zusatz.

## Abgrenzung zu G1b

`api/kronos/google_import.py` enthält `_require_import_admin`,
`_get_settings(db)`, `_ensure_kalender(name, color, db=None)` und
`_create_element_from_dict(fields, db=None)`. Diese Schreib-Helfer lassen sich
in einer bestehenden Transaktion verwenden und committen dann nicht selbst;
ohne Session öffnen sie eine eigene Transaktion. Element-Felder werden
normalisiert.

Der Google-Teil muss zeitzonenbehaftete Zeitpunkte ebenfalls in
`CALENDAR_TIMEZONE` umrechnen, bevor er sie offsetlos an die Schreib-Helfer
übergibt, und Geheimnisse ausschließlich über
`diakronos_app.google_secrets.encrypt_secret/decrypt_secret` schreiben und
lesen. Kein ungefilterter Google-Fehlertext in Antworten oder Logs.

## Verifikation

Belegt ist G1a durch gezielte Tests der Import-Logik mit einer echten
`.ics`-Beispieldatei (`backend/tests/fixtures/google_import.ics`), eine echte
HTTP-Prüfung mit Anmeldung und CSRF-Kopf gegen eine Wegwerf-Datenbank
(Originalpfade: Gast 403, Administrator 200; fünf Termine importiert, beim
zweiten Lauf fünf übersprungen, Testdaten danach entfernt) und eine Prüfung der
Migration gegen eine Wegwerf-Datenbank (Verschlüsselung vorhandener
Klartextwerte, `upgrade`, `downgrade`, zweimal `alembic check` ohne neue
Operationen). Die vollständige Python-Suite läuft im Image grün.

**Ein echter Import gegen einen laufenden Betriebsstack und ein echter
Google-Rundlauf sind nicht geprüft** und werden hier nicht als erledigt
bezeichnet.
