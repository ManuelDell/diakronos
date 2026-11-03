# Änderungen

Alle nennenswerten Änderungen an Diakronos. Die Versionen folgen der
[Semantischen Versionierung](https://semver.org/lang/de/).

## Unveröffentlicht

### Funktionen

- **ON-1 — Einrichtungslink beim ersten Start.** Ist noch kein Benutzer
  vorhanden und sind `ADMIN_EMAIL`/`ADMIN_PASSWORD` nicht gesetzt, erzeugt der
  Start einen einmaligen Einrichtungs-Token (43 Zeichen) und gibt ihn als
  Kasten auf stdout aus; in der Datenbank steht nur sein SHA-256-Hash mit
  Ablauf (7 Tage, Tabelle `einrichtung_token`). Die Seite
  `/einrichtung/<token>` („Administrator anlegen", Entwurf 02/13) legt in EINER
  Transaktion Benutzer + Rollen (System Manager, Mitgliederadministrator) und
  das zugehörige Mitglied an, verbraucht den Link und meldet den neuen
  Administrator direkt an; ein ungültiger, abgelaufener oder verbrauchter Link
  liefert stets dieselbe Seite „Dieser Einrichtungslink ist nicht mehr gültig"
  (Entwurf 03, Status 404). Neuen Link erzeugen:
  `docker compose exec app diakronos einrichtungslink`. Der Weg über
  `ADMIN_EMAIL`/`ADMIN_PASSWORD` bleibt unverändert (dann entsteht kein Link).
  Siehe Betriebsanleitung 2.3.

### Sicherheit

- **ON-1b — Nachbesserung Einrichtungslink (Opus-Review).** Der Token des
  Einrichtungslinks erscheint **nicht mehr im Zugriffsprotokoll**: ein Filter
  am `uvicorn.access`-Logger schreibt `/einrichtung/<token>` zu
  `/einrichtung/***` um (Betriebs-Präfix und Query bleiben lesbar). Reverse-
  Proxy-Logs (nginx/NPM) protokollieren den Pfad weiterhin selbst — der
  Hinweis samt Schutzempfehlung steht in der Betriebsanleitung 2.3. Nach einem
  Validierungsfehler ist das Formular **erneut absendbar** (die Fehlerseite
  trägt jetzt ein frisches `_csrf`; vorher endete der zweite Versuch im
  Browser mit 403). Der GET der Seite **schreibt nicht mehr** (Diagnose-Zähler
  `aufrufe` unverändert). Ein ungültiger Token liefert **immer** „Link
  ungültig" (404), auch wenn zusätzlich Formularfelder falsch sind — die
  Meldung „Passwort zu mindestens 12 Zeichen" verriet sonst indirekt, dass der
  Token gültig war. Die Sitzung nach dem Anlegen ist **keine SSO-Sitzung**
  mehr und unterliegt damit der Wechselpflicht. Zwei parallele Absendungen
  legen auf PostgreSQL dank Zeilensperre genau **einen** Benutzer an (Test).
  Tote Konstanten `CSP`/`ANTWORT_KOPFZEILEN` entfernt. Der Startkasten nennt
  den Link jetzt **mit `DIAKRONOS_BASE_PATH`** — vorher zeigte er
  `/einrichtung/<token>`, was im Präfix-Betrieb mit 404 antwortet. Siehe
  Betriebsanleitung 2.3 (Reverse-Proxy-Logs; „werden alle Benutzer gelöscht,
  erscheint beim nächsten Start wieder ein Link").

- **SEC-11b — restliche schreibende GET-Endpunkte, echtes Inventar.**
  `schliesse_mitglied_aus`, `register_mitglied`, `speichere_plan_entwurf`,
  `submit_registrierung`, `submit_gast` und `get_oauth_url` (schreibt den
  OAuth-State nach Redis) nehmen nur noch POST an; ein GET endet mit 405 und
  führt nichts aus. Das Inventar (`tools/whitelist_inventar.py`) stuft
  „lesend" nicht mehr nach dem Namen ein, sondern prüft den Funktionsrumpf
  (AST, `tools/whitelist_lesen.py`); jeder verbleibende Widerspruch steht mit
  Begründung in `AUSNAHMEN` (lesend 149, schreibend 172, offen 0). Der Wächter
  schlüsselt nach `modul.name` (gleichnamige Funktionen überschrieben sich)
  und die C4-Ausnahme ist eine exakte Namensmenge statt `website.*`.

## 2.0.0 — 2026-10-22

Neuentwicklung: eigenständig neu gebaut mit FastAPI, PostgreSQL und Vue-SPA,
ausgeliefert als Docker-Compose-Stack, **ohne Frappe**. Die frühere
Frappe-App wird nicht mehr weiterentwickelt; ihr Stand bleibt als
`legacy/`-Branches erhalten.

### Funktionen

- **Mitglieder** — Mitgliederliste mit Suche, Detailseite, Status (aktiv,
  Gast, ausgetreten), Konten, Rollen, Adressbuch mit einstellbarer Sichtbarkeit.
- **Familien und Gruppen** — Gruppen und Dienste mit Mitgliedschaften,
  Gruppenrechte, Organigramm als zweite Ansicht der Gruppenseite.
- **Kalender** — Monats-, Wochen- und Tagesansicht, mehrere Kalender mit
  Farben und Zugriffsrechten, wiederkehrende Termine, Raumbelegung,
  Moderations-Workflow für Terminvorschläge, Suche.
- **CalDAV** — Kalenderabruf für Apple Kalender, Thunderbird, DAVx⁵ und
  andere über `/dav/` (nur lesend).
- **Kalender-Import** — iCal-Datei hochladen; Google Kalender anbinden und im
  Hintergrund importieren.
- **Ressourcen** — Räume und Ressourcen verwalten, Buchungen mit
  Doppelbuchungs-Prüfung.
- **Dienste und Dienstplan** — Dienstrollen, Dienstpläne je Zeitraum,
  „Meine Dienste“ für jedes Mitglied.
- **Plan-Rahmen** — Terminpläne (z. B. Gottesdienst-Ablauf, Chorplan) mit
  Feldern je Termin, Entwurf und Veröffentlichung, Vorlagen aus einem Kochbuch.
- **Lieder** — Lieder und Liedgruppen, Liedzuteilung in Plänen, Noten- und
  Audiodateien.
- **Registrierung und Anmeldung** — Selbstregistrierung mit Prüfweg,
  Registrierungslinks, Profilseite, optionale Anmeldung über einen externen
  OIDC-Anbieter.
- **Austritt** — Austritt/Deaktivieren durch einen Administrator, umkehrbar
  über „Reaktivieren“.
- **Mailversand** — SMTP-Postfach wird vom System Manager in der Oberfläche
  eingerichtet (Passwort verschlüsselt gespeichert, Testmail); genutzt u. a.
  für die Löschung auf Antrag.
- **Datenschutz** — Einwilligungen, Auskunft als JSON-Ausfuhr, Löschung auf
  Antrag, Nachweis der Löschung.
- **Datensicherung** — Automatische tägliche Sicherung von Datenbank und
  Dateiablage, Aufbewahrungsfrist, Wiederherstellung über die Kommandozeile.

### Betrieb

- Docker-Compose-Stack aus einem Image (Anwendung, Hintergrundarbeit,
  Zeitpläne); die Datenbank wird beim Start automatisch migriert.
- Rechte über Rollen (System Manager, Mitgliederadministrator,
  Kalenderadministrator, Kalender-Moderator, Mitglied) und über die
  Sichtbarkeitseinstellung der Person.
- Anmeldesperre gegen Durchprobieren, HTTPS über den mitgelieferten nginx
  oder einen eigenen Reverse-Proxy, Konfiguration ausschließlich über `.env`.

## Unveröffentlicht

### Sicherheit (SEC-3, Pentest dev.ecg-hn.de)

- **Registrierungslink-Token** — der Token eines NEUEN Links entsteht immer
  serverseitig als starkes Zufallstoken (`secrets.token_urlsafe(32)`,
  43 Zeichen); ein beim Anlegen mitgeschickter `slug` wird verworfen — auch
  über `POST /api/resource/Registrierungslink`. **Bestehende Links bleiben
  unverändert gültig** (der gespeicherte Slug wird nicht angefasst).
- **Ratenbegrenzung der Registrierung** — ein überschrittenes Limit auf
  `validate_token` und `submit_registrierung` antwortet jetzt mit HTTP **429**
  (`RateLimitError`) statt 417; Skripte und Monitore können „zu viele
  Versuche“ damit von „ungültige Eingabe“ unterscheiden. Die Grenzen
  (`REGISTRIERUNG_MAX_*`) sind unverändert.
- Migration `sec3_reglink_token` ändert **keine Daten**; sie vermerkt in der
  neuen Tabelle `schema_stand`, dass die Installation die starke Tokenform
  kennt.

