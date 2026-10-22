# Google-Kalender-Import: Einstieg

Überblick über den Kalenderimport (iCal-Datei und Google). Die Einzelheiten
stehen in den drei Themendokumenten:

- [G1a](G1A-GOOGLE-IMPORT.md): iCal-Upload, verschlüsselte Zugangsdaten, Zeitvertrag
- [G1b](G1B-GOOGLE-OAUTH.md): Google-Anmeldung, Google-API, Hintergrundimport, Callback, Cloud-Console-Anleitung
- [G2](G2-KALENDER-IMPORT.md): die Importseite in der Oberfläche und ihre Prüfung

Für Betreiber: [BETRIEBSANLEITUNG.md](BETRIEBSANLEITUNG.md) Abschnitt 5.6.

## Architektur in Kürze

1. **Oberfläche:** `frontend/src/diakonos/pages/KalenderImport.vue`, Route
   `#/kalender/import` (Navigation „Kalender importieren“). Alle Aufrufe laufen
   über `apiCall()`.
2. **API:** `/api/method/diakronos.kronos.api.google_import.<funktion>`
   (`api/kronos/google_import.py`): `get_credentials_status`, `save_credentials`,
   `upload_ical`, `get_oauth_url`, `exchange_code`, `get_google_calendars`,
   `start_import`.
3. **Callback-Route:** `GET /google-calendar-callback` (`google_callback.py`).
   Tauscht den Code gegen Tokens und leitet per 303 auf
   `/diakonos?gcal_step=2#/kalender/import` bzw. `?gcal_error=...` weiter (nur
   allgemeine Meldungen). Die Redirect-URI ist immer
   `https://<host>/google-calendar-callback`.
4. **Import:** `start_import` reiht `_do_import` in die Warteschlange `default`
   ein (Worker-Container, Zeitlimit 600 s). Der Auftrag schreibt Termine in die
   Kalendertabelle; Dubletten werden über stabile Hashes der Ereignis-ID
   übersprungen.
5. **Fortschritt:** Der Worker veröffentlicht über Redis, der Anwendungsserver
   liefert es per Socket.IO (`gcal_import_progress`) an den angemeldeten
   Benutzer.
6. **OAuth-State:** 32 Zufallsbytes in Redis, 600 Sekunden, einmalig
   verwendbar, an Sitzung und aktuelle Zugangsdaten gebunden.
7. **Verschlüsselung:** `google_secrets.py`, Fernet, Schlüssel = SHA-256 über
   Präfix und `SECRET_KEY`. `client_secret` und `token_data` liegen nur
   verschlüsselt in der Datenbank. `SECRET_KEY` muss stabil bleiben; der
   frühere Platzhalter `insecure-dev-key` und ein leerer Wert werden verweigert
   (die Compose-Vorgabe von damals gibt es seit PUB-4f nicht mehr, `.env`
   verlangt einen echten Wert). Es gibt keinen Klartext-Rückfallweg.
8. **Rechte:** Das Backend erlaubt `Administrator`, `System Manager`,
   `Mitgliederadministrator` und `Kalenderadministrator`; alle Endpunkte sind
   für Gäste gesperrt, der Worker prüft nach der Wartezeit erneut. Der Link in
   der Navigation zeigt sich nur `Administrator` und `Kalenderadministrator`.
9. **Umfang:** nur `https://www.googleapis.com/auth/calendar.readonly`;
   einmaliger Import, keine Synchronisierung; ein Google-Konto je Installation.

## Stand

Belegt ist der iCal-Import (Tests, Wegwerf-Datenbank, echter Browser) und der
Google-Ablauf gegen ein nachgebautes Google (Tests und Browser mit simulierten
Antworten). **Nicht belegt: ein echter Rundlauf mit einem echten Google-Konto** —
dafür sind die Zugangsdaten des Betreibers nötig (Anleitung in
[G1b](G1B-GOOGLE-OAUTH.md)).
