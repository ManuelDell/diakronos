# Kalenderimport innerhalb der Anwendung (G2)

## Umsetzung

Seite `/diakonos#/kalender/import`, lazy geladen durch `router.js`; die
Navigation führt mit `navigate()` dorthin. Die Sichtbarkeit bleibt auf
Administrator/Kalenderadministrator beschränkt. Die Rollen kommen aus der
Anmeldesitzung (`session.get_current_user_context`), nicht aus einem
Seiten-Global — vorher blieb der Link deshalb auch für berechtigte Benutzer
verborgen. Der Gast-Schutz bleibt unverändert: ein direkter Aufruf der
Import-Adresse als Gast führt auf die Startseite zurück.

**Google-Reiter:** Status laden, Client-ID/Secret/Redirect-URI speichern,
Google-Autorisierung, Zuordnung der Kalender auf neue oder bestehende Ziele,
Farbe und Zeitfilter, Alle/Keine-Auswahl, Hintergrundimport mit Live-Fortschritt
und Abschlussbilanz.

Rückkehrparameter aus dem Google-Ablauf (`gcal_step`, `gcal_error`) werden vor
dem Auswerten aus der Adresse entfernt (`history.replaceState`); andere
Parameter bleiben erhalten. Fehler aus der Adresse oder vom Server werden
niemals roh angezeigt. Die Zieladresse ist auf
`https://accounts.google.com/o/oauth2/v2/auth` beschränkt.

Das Client-Secret wird nur in ein Passwortfeld eingegeben und nie
zurückgeladen; beim Speichern (auch bei Fehler) und beim Verlassen wird das Feld
geleert. Keine Geheimnisse in Logs, HTML-Attributen, LocalStorage oder
Fehlermeldungen. Namen werden als Text interpoliert, kein `v-html`. Prüfung der
Berechtigung und Verschlüsselung des Secrets bleiben im Backend (G1a/G1b).

**iCal-Reiter:** echte `.ics`-Datei, neuer Name/Farbe oder bestehender
Zielkalender, Dateiprüfung (nicht leer, maximal 5 MiB), Base64 der originalen
Dateibytes (UTF-8 bleibt unverändert), Ergebnis und aktualisierte
Kalenderliste. Die Ziele kommen aus einer eigenen Abfrage der schreibbaren
Kalender, nicht aus einem Frappe-Desk-Aufruf, den es hier nicht gibt.

**Fortschritt:** Socket.IO verbindet vor dem Einreihen und verwendet
Sitzungscookies und den CSRF-Kopf aus den Startdaten der Seite. Ohne diesen
Kopf scheiterte das Absenden mit 417; eine globale CSRF-Ausnahme gibt es nicht.
Listener und Socket werden bei Abschluss, Startfehler oder Verlassen entfernt.
Bei Verbindungsabbruch oder fehlender Abschlussmeldung nach elf Minuten wird
kein Erfolg behauptet und kein zweiter Import ausgelöst. Der Serverauftrag
läuft beim Verlassen der Seite weiter; vor einem erneuten Import den Kalender
prüfen.

## Prüfung

Abgedeckt sind Callback-Bereinigung, Secret-Cleanup, Zuordnung,
Socket-Verbindung vor dem Einreihen, CSRF-Kopf, Fehlerpfade, Erhalt der
UTF-8-Bytes, Rollen und der Gast-Schutz — als Node-Tests
(`node --test frontend/tests/*.test.mjs`) und in der Python-Suite im Image.
Dazu kommt eine Browser-Prüfung mit Chromium/Playwright gegen einen isolierten
Stack: Anmeldung über die normale Maske, tatsächlicher Klick in der Navigation
öffnet die Seite, keine Fehler beim Aufbau.

Der iCal-Import wurde mit einer Beispieldatei über das echte Dateifeld geprüft:
beim ersten Lauf werden alle Ereignisse angelegt, beim zweiten Lauf in denselben
Kalender werden sie als bereits vorhanden übersprungen. Der Google-Ablauf wurde
mit simulierten Antworten des Anbieters, aber echtem Socket.IO und echtem
Fortschritts-Ereignis geprüft. **Ein Durchlauf mit echten Google-Zugangsdaten
steht noch aus** — Anleitung dazu:
[G1b Cloud Console](G1B-GOOGLE-OAUTH.md#google-cloud-console--der-manuelle-echte-rundlauf).
