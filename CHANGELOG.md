# Änderungen

Alle nennenswerten Änderungen an Diakronos. Die Versionen folgen der
[Semantischen Versionierung](https://semver.org/lang/de/).

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

