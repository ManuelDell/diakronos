# Inventar der whitelist-Funktionen (SEC-11 C2, verschaerft SEC-11b F2)

Erzeugt von `tools/whitelist_inventar.py` — nicht von Hand bearbeiten.
Grundlage: das lebende Register `diakronos_app.frappe_compat.registry`
nach dem Import aller API-Module, dazu der Funktionsrumpf aus dem AST
(`tools/whitelist_lesen.py`).

* registrierte Pfade: **1766**
* eindeutige Funktionen: **343**
* lesend: **158**, schreibend: **185**
* Rumpfbefund: schreibend 175, lesend 168, unbekannt 0

## Einstufung

`schreibend` = veraendert DB/Redis/Dateien, versendet Mail oder legt ein
Token/eine Sitzung an. Im Zweifel schreibend. Schreibende Endpunkte
tragen `@whitelist(methods=["POST"])`; der Router lehnt dann jede andere
Methode mit 405 ab (Browser-Navigation: 303 auf die Anmeldemaske).

**Lesend gilt nur, wenn weder Rumpf noch Name noch Deklaration schreiben.**
Der Rumpfbefund (AST) ist maßgeblich: erkannt werden `_update_doc`,
`insert`, `commit`, `session.add/merge/delete`, `set_value`, `db.set`,
Redis `set`/`setex`/`delete`, Dateischreiben, SQL, die Praefixe
`sende_*`/`benachrichtig*`/`*notify*`/`enqueue*` und — eine Ebene tief —
Hilfsfunktionen (im selben Modul UND importierte `diakronos_app.*`-Helfer
mit Modulbezug, SEC-11c/R1). Der Name ist Hinweis, nicht Urteil.

## Widersprueche (Rumpf / Name / Deklaration)

| Funktion | Methoden | Rumpf | Name | Deklariert | Grund |
|---|---|---|---|---|---|
| `diakronos_app.api.einrichtung.erinnern_spaeter` | ['POST'] | schreibend | lesend | schreibend | Aufruf sess.commit() |
| `diakronos_app.api.einrichtung.kalender_vorschlag_anlegen` | ['POST'] | lesend | schreibend | schreibend |  |
| `diakronos_app.api.kronos.google_import.get_oauth_url` | ['POST'] | schreibend | lesend | schreibend | Aufruf _state_store.set() |

Entschieden ohne Ausnahme (Quellen einig, die Grenze traegt die Deklaration — keine offene Frage):

* `diakronos_app.api.website.bausteine_installieren` (Methoden ['POST'])

## Ausnahmen (lesend trotz Widerspruch, mit Begruendung)

| Funktion | Methoden | Rumpf | Name | Ausnahme | Art | Greift |
|---|---|---|---|---|---|---|
| `diakronos_app.anmeldung.einstellungen_api.anmeldung_get_einstellungen` | — | schreibend | lesend | Leseansicht; legt fehlende Konfigurationszeile an (Helfer erkannt) | konfig — Leseansicht, die beim ERSTEN Aufruf ihre Konfigurationszeile anlegt (idempotent, ohne Absicht des Nutzers) — der POST waere hier falsch | ja (rumpf) |
| `diakronos_app.api.frappe_core.logout` | ['POST'] | lesend | schreibend | loescht nur die eigene Sitzung (Abmelden), keine Fachdaten | rueckkanal — der Rumpf loescht nur die eigene Sitzung/den eigenen Token (Abmelden), er aendert keine Fachdaten | ja (name, deklaration) |
| `diakronos_app.api.gemeinde.datenschutz_get_texte` | — | schreibend | lesend | Leseansicht; legt fehlende Textzeile an (Helfer erkannt) | konfig — Leseansicht, die beim ERSTEN Aufruf ihre Konfigurationszeile anlegt (idempotent, ohne Absicht des Nutzers) — der POST waere hier falsch | ja (rumpf) |
| `diakronos_app.api.gemeinde.gemeinde_get_einstellungen` | — | schreibend | lesend | Leseansicht; legt fehlende Konfigurationszeile an (Helfer erkannt) | konfig — Leseansicht, die beim ERSTEN Aufruf ihre Konfigurationszeile anlegt (idempotent, ohne Absicht des Nutzers) — der POST waere hier falsch | ja (rumpf) |
| `diakronos_app.api.gruppen.get_user_create_permissions` | — | lesend | schreibend | liest Rechte, schreibt nichts | name — Namensbefund ohne Rumpfbefund — geprueft, die Funktion liest nur | ja (name) |
| `diakronos_app.api.kronos.google_import.get_credentials_status` | — | schreibend | lesend | liest mit Zeiliensperre, schreibt nichts | sperre — liest mit Zeiliensperre (`with_for_update`), schreibt nichts | ja (rumpf) |
| `diakronos_app.api.kronos.google_import.get_google_calendars` | — | schreibend | lesend | liest mit Zeiliensperre, schreibt nichts | sperre — liest mit Zeiliensperre (`with_for_update`), schreibt nichts | ja (rumpf) |
| `diakronos_app.api.kronos.google_import.get_import_progress` | — | lesend | schreibend | liest nur den Fortschritt aus Redis | name — Namensbefund ohne Rumpfbefund — geprueft, die Funktion liest nur | ja (name) |
| `diakronos_app.api.mitglieder.import_mitglieder_vorschau` | ['POST'] | lesend | schreibend | reine Vorschau des CSV-Imports, schreibt keine Zeile | nur_vorschau — Namensbefund/Weiterleitung ohne Wirkung: die Funktion schreibt nicht oder die Schreibung haengt an einem Schalter, der per Default aus ist | ja (name, deklaration) |
| `diakronos_app.api.planrahmen.plan_entwurf` | ['POST'] | schreibend | lesend | Lesezugriff ueber den Schreib-Wrapper (`_endpunkt(True)`); POST ist die Grenze des Wrappers, der Name meint das Lesen des Entwurfs | nur_vorschau — Namensbefund/Weiterleitung ohne Wirkung: die Funktion schreibt nicht oder die Schreibung haengt an einem Schalter, der per Default aus ist | ja (rumpf, deklaration) |
| `diakronos_app.api.planrahmen.undo_vorschau` | — | lesend | schreibend | Vorschau, schreibt nichts | name — Namensbefund ohne Rumpfbefund — geprueft, die Funktion liest nur | ja (name) |
| `diakronos_app.api.profile.delete_my_data` | ['POST'] | lesend | schreibend | abgeschalteter Altpfad — wirft nur den Hinweis auf den Loeschantrag | nur_vorschau — Namensbefund/Weiterleitung ohne Wirkung: die Funktion schreibt nicht oder die Schreibung haengt an einem Schalter, der per Default aus ist | ja (name, deklaration) |
| `diakronos_app.api.sicherung.sicherung_get` | — | schreibend | lesend | Leseansicht; legt fehlende Einstellungszeile an | konfig — Leseansicht, die beim ERSTEN Aufruf ihre Konfigurationszeile anlegt (idempotent, ohne Absicht des Nutzers) — der POST waere hier falsch | ja (rumpf) |
| `diakronos_app.api.website.beitrag_auf_website` | ['POST'] | schreibend | lesend | Methode wird im Rumpf geprueft (`_nur_post` -> 405) | schranke — prüft die Methode selbst (`_nur_post`) und weist alles ausser POST mit 405 ab — die Grenze steht im Rumpf, nicht in der Deklaration | ja (rumpf, deklaration) |
| `diakronos_app.api.website.freigaben_lesen` | — | lesend | schreibend | Leseansicht der Website-Freigaben | name — Namensbefund ohne Rumpfbefund — geprueft, die Funktion liest nur | ja (name) |
| `diakronos_app.api.website.kategorie_oeffentlich` | ['POST'] | schreibend | lesend | Methode wird im Rumpf geprueft (`_nur_post` -> 405) | schranke — prüft die Methode selbst (`_nur_post`) und weist alles ausser POST mit 405 ab — die Grenze steht im Rumpf, nicht in der Deklaration | ja (rumpf, deklaration) |
| `diakronos_app.api.website.login_uebergabe` | ['POST'] | lesend | schreibend | stellt nur einen Token/URL aus, schreibt keine Fachdaten | rueckkanal — der Rumpf loescht nur die eigene Sitzung/den eigenen Token (Abmelden), er aendert keine Fachdaten | ja (name, deklaration) |

Ausnahmen OHNE Wirkung (die Funktion ist ohnehin schreibend — Eintrag entfernen):

* `diakronos_app.api.fail_validation`

## Schreibende Funktionen

| Funktion | Methoden | Gast |
|---|---|---|
| `diakronos_app.anmeldung.einstellungen_api.anmeldung_get_einstellungen` | — | nein |
| `diakronos_app.anmeldung.einstellungen_api.anmeldung_setze_rollen_zuordnung` | ['POST'] | nein |
| `diakronos_app.anmeldung.einstellungen_api.anmeldung_setze_unbekannte_nutzer` | ['POST'] | nein |
| `diakronos_app.anmeldung.einstellungen_api.anmeldung_speichern` | ['POST'] | nein |
| `diakronos_app.api.admin_hub.create_anmeldeformular` | ['POST'] | nein |
| `diakronos_app.api.admin_hub.delete_anmeldeformular` | ['POST'] | nein |
| `diakronos_app.api.admin_hub.genehmige_anmeldung` | ['POST'] | nein |
| `diakronos_app.api.admin_hub.lehne_anmeldung_ab` | ['POST'] | nein |
| `diakronos_app.api.admin_hub.update_anmeldeformular` | ['POST'] | nein |
| `diakronos_app.api.admin_hub.update_anmeldeformular_felder` | ['POST'] | nein |
| `diakronos_app.api.audit.mark_notifications_read` | ['POST'] | nein |
| `diakronos_app.api.austritt.mitglied_austritt` | ['POST'] | nein |
| `diakronos_app.api.austritt.mitglied_reaktivieren` | ['POST'] | nein |
| `diakronos_app.api.auth.login` | ['POST'] | ja |
| `diakronos_app.api.auth.logout` | ['POST'] | ja |
| `diakronos_app.api.beitraege.create_beitrag` | ['POST'] | nein |
| `diakronos_app.api.beitraege.create_kommentar` | ['POST'] | nein |
| `diakronos_app.api.beitraege.delete_beitrag` | ['POST'] | nein |
| `diakronos_app.api.beitraege.update_beitrag` | ['POST'] | nein |
| `diakronos_app.api.bugreport.melden` | ['POST'] | nein |
| `diakronos_app.api.bugreport.set_status` | ['POST'] | nein |
| `diakronos_app.api.dashboard.reset_user_config` | ['POST'] | nein |
| `diakronos_app.api.dashboard.set_user_config` | ['POST'] | nein |
| `diakronos_app.api.datenschutz.anonymisieren` | ['POST'] | nein |
| `diakronos_app.api.datenschutz.loeschantrag_ablehnen` | ['POST'] | nein |
| `diakronos_app.api.datenschutz.loeschantrag_zurueckziehen` | ['POST'] | nein |
| `diakronos_app.api.datenschutz.loeschung_beantragen` | ['POST'] | nein |
| `diakronos_app.api.datenschutz.loeschung_bestaetigen` | ['POST'] | nein |
| `diakronos_app.api.einrichtung.abschliessen` | ['POST'] | nein |
| `diakronos_app.api.einrichtung.erinnern_spaeter` | ['POST'] | nein |
| `diakronos_app.api.einrichtung.kalender_vorschlag_anlegen` | ['POST'] | nein |
| `diakronos_app.api.einrichtung.schritt_setzen` | ['POST'] | nein |
| `diakronos_app.api.entsperren.entsperren_konto` | ['POST'] | nein |
| `diakronos_app.api.frappe_core.insert` | ['POST'] | nein |
| `diakronos_app.api.frappe_core.logout` | ['POST'] | ja |
| `diakronos_app.api.frappe_core.upload_file` | ['POST'] | nein |
| `diakronos_app.api.gemeinde.datenschutz_get_texte` | — | nein |
| `diakronos_app.api.gemeinde.datenschutz_speichern` | ['POST'] | nein |
| `diakronos_app.api.gemeinde.gemeinde_get_einstellungen` | — | nein |
| `diakronos_app.api.gemeinde.gemeinde_logo_entfernen` | ['POST'] | nein |
| `diakronos_app.api.gemeinde.gemeinde_logo_hochladen` | ['POST'] | nein |
| `diakronos_app.api.gemeinde.gemeinde_setze_linkvorgaben` | ['POST'] | nein |
| `diakronos_app.api.gemeinde.gemeinde_setze_modul` | ['POST'] | nein |
| `diakronos_app.api.gemeinde.gemeinde_speichern` | ['POST'] | nein |
| `diakronos_app.api.gruppen.add_mitglied_to_gruppe` | ['POST'] | nein |
| `diakronos_app.api.gruppen.create_ankuendigung` | ['POST'] | nein |
| `diakronos_app.api.gruppen.create_aufgabe` | ['POST'] | nein |
| `diakronos_app.api.gruppen.create_dienstbereich` | ['POST'] | nein |
| `diakronos_app.api.gruppen.create_gruppe` | ['POST'] | nein |
| `diakronos_app.api.gruppen.create_untergruppe` | ['POST'] | nein |
| `diakronos_app.api.gruppen.get_user_create_permissions` | — | nein |
| `diakronos_app.api.gruppen.remove_mitglied_from_gruppe` | ['POST'] | nein |
| `diakronos_app.api.gruppen.toggle_aufgabe` | ['POST'] | nein |
| `diakronos_app.api.gruppen.update_dienstbereich` | ['POST'] | nein |
| `diakronos_app.api.gruppen.update_gruppe` | ['POST'] | nein |
| `diakronos_app.api.gruppen.update_mitglied_rolle` | ['POST'] | nein |
| `diakronos_app.api.gruppen.update_untergruppe` | ['POST'] | nein |
| `diakronos_app.api.kronos.ablaufplan_api.save_ablaufplan` | ['POST'] | nein |
| `diakronos_app.api.kronos.event_crud.aenderung_ablehnen` | ['POST'] | nein |
| `diakronos_app.api.kronos.event_crud.aenderung_freigeben` | ['POST'] | nein |
| `diakronos_app.api.kronos.event_crud.create_event` | ['POST'] | nein |
| `diakronos_app.api.kronos.event_crud.create_series` | ['POST'] | nein |
| `diakronos_app.api.kronos.event_crud.delete_event` | ['POST'] | nein |
| `diakronos_app.api.kronos.event_crud.save_event` | ['POST'] | nein |
| `diakronos_app.api.kronos.event_crud.update_event` | ['POST'] | nein |
| `diakronos_app.api.kronos.google_import.exchange_code` | ['POST'] | nein |
| `diakronos_app.api.kronos.google_import.get_credentials_status` | — | nein |
| `diakronos_app.api.kronos.google_import.get_google_calendars` | — | nein |
| `diakronos_app.api.kronos.google_import.get_import_progress` | — | nein |
| `diakronos_app.api.kronos.google_import.get_oauth_url` | ['POST'] | nein |
| `diakronos_app.api.kronos.google_import.save_credentials` | ['POST'] | nein |
| `diakronos_app.api.kronos.google_import.start_import` | ['POST'] | nein |
| `diakronos_app.api.kronos.google_import.upload_ical` | ['POST'] | nein |
| `diakronos_app.api.kronos.kalender_verwaltung.create_kalender` | ['POST'] | nein |
| `diakronos_app.api.kronos.kalender_verwaltung.delete_kalender` | ['POST'] | nein |
| `diakronos_app.api.kronos.kalender_verwaltung.update_kalender` | ['POST'] | nein |
| `diakronos_app.api.kronos.kanban_api.finalize_staged_events` | ['POST'] | nein |
| `diakronos_app.api.kronos.kanban_api.resolve_conflict` | ['POST'] | nein |
| `diakronos_app.api.kronos.kanban_api.save_staging_state` | ['POST'] | nein |
| `diakronos_app.api.kronos.series.delete_future_series_events` | ['POST'] | nein |
| `diakronos_app.api.kronos.series.delete_series_batch_fast` | ['POST'] | nein |
| `diakronos_app.api.kronos.series.update_series_batch_fast` | ['POST'] | nein |
| `diakronos_app.api.mailversand.mailversand_speichern` | ['POST'] | nein |
| `diakronos_app.api.mailversand.mailversand_testmail` | ['POST'] | nein |
| `diakronos_app.api.mitglieder.create_mitglied` | ['POST'] | nein |
| `diakronos_app.api.mitglieder.import_mitglieder_uebernehmen` | ['POST'] | nein |
| `diakronos_app.api.mitglieder.import_mitglieder_vorschau` | ['POST'] | nein |
| `diakronos_app.api.mitglieder.schliesse_mitglied_aus` | ['POST'] | nein |
| `diakronos_app.api.mitglieder.set_mitglied_status` | ['POST'] | nein |
| `diakronos_app.api.mitglieder.update_mitglied` | ['POST'] | nein |
| `diakronos_app.api.mitglieder.update_mitglied_with_confirmation` | ['POST'] | nein |
| `diakronos_app.api.mitglieder.widerruf_einwilligung` | ['POST'] | nein |
| `diakronos_app.api.planrahmen.ablauf_aendern` | ['POST'] | nein |
| `diakronos_app.api.planrahmen.abwesenheit_loeschen` | ['POST'] | nein |
| `diakronos_app.api.planrahmen.abwesenheit_melden` | ['POST'] | nein |
| `diakronos_app.api.planrahmen.dienst_absagen` | ['POST'] | nein |
| `diakronos_app.api.planrahmen.eintrag_loesen` | ['POST'] | nein |
| `diakronos_app.api.planrahmen.eintrag_setzen` | ['POST'] | nein |
| `diakronos_app.api.planrahmen.lied_material_hinzufuegen` | ['POST'] | nein |
| `diakronos_app.api.planrahmen.lied_material_loeschen` | ['POST'] | nein |
| `diakronos_app.api.planrahmen.lied_speichern` | ['POST'] | nein |
| `diakronos_app.api.planrahmen.merkmale_pflegen` | ['POST'] | nein |
| `diakronos_app.api.planrahmen.plan_aendern` | ['POST'] | nein |
| `diakronos_app.api.planrahmen.plan_anlegen` | ['POST'] | nein |
| `diakronos_app.api.planrahmen.plan_archivieren` | ['POST'] | nein |
| `diakronos_app.api.planrahmen.plan_entwurf` | ['POST'] | nein |
| `diakronos_app.api.planrahmen.plan_generieren` | ['POST'] | nein |
| `diakronos_app.api.planrahmen.plan_kopieren` | ['POST'] | nein |
| `diakronos_app.api.planrahmen.plan_loeschen` | ['POST'] | nein |
| `diakronos_app.api.planrahmen.plantyp_speichern` | ['POST'] | nein |
| `diakronos_app.api.planrahmen.platz_hinzufuegen` | ['POST'] | nein |
| `diakronos_app.api.planrahmen.sammlung_pflegen` | ['POST'] | nein |
| `diakronos_app.api.planrahmen.sammlungsmerkmal_werte_pflegen` | ['POST'] | nein |
| `diakronos_app.api.planrahmen.termin_aendern` | ['POST'] | nein |
| `diakronos_app.api.planrahmen.termin_entfernen` | ['POST'] | nein |
| `diakronos_app.api.planrahmen.termin_hinzufuegen` | ['POST'] | nein |
| `diakronos_app.api.planrahmen.undo` | ['POST'] | nein |
| `diakronos_app.api.planrahmen.undo_vorschau` | — | nein |
| `diakronos_app.api.planrahmen.veroeffentlichen` | ['POST'] | nein |
| `diakronos_app.api.planung.create_plan` | ['POST'] | nein |
| `diakronos_app.api.planung.generiere_plan` | ['POST'] | nein |
| `diakronos_app.api.planung.generiere_rotation` | ['POST'] | nein |
| `diakronos_app.api.planung.set_position_verantwortlicher` | ['POST'] | nein |
| `diakronos_app.api.planung.set_rollenbesetzung` | ['POST'] | nein |
| `diakronos_app.api.planung.speichere_plan_entwurf` | ['POST'] | nein |
| `diakronos_app.api.planung.veroeffentliche_plan` | ['POST'] | nein |
| `diakronos_app.api.planung.zurueckziehen_plan` | ['POST'] | nein |
| `diakronos_app.api.profile.delete_my_data` | ['POST'] | nein |
| `diakronos_app.api.profile.update_adressbuch_sichtbarkeit` | ['POST'] | nein |
| `diakronos_app.api.profile.update_einwilligung` | ['POST'] | nein |
| `diakronos_app.api.profile.update_my_profile` | ['POST'] | nein |
| `diakronos_app.api.profile.update_profile_picture` | ['POST'] | nein |
| `diakronos_app.api.psalmos.musik.delete_liedgruppe` | ['POST'] | nein |
| `diakronos_app.api.psalmos.musik.save_fassung` | ['POST'] | nein |
| `diakronos_app.api.psalmos.musik.save_lied` | ['POST'] | nein |
| `diakronos_app.api.psalmos.musik.save_liedgruppe` | ['POST'] | nein |
| `diakronos_app.api.registrierung.submit_gast` | ['POST'] | ja |
| `diakronos_app.api.registrierung.submit_registrierung` | ['POST'] | ja |
| `diakronos_app.api.registrierungslink_api.create_link` | ['POST'] | nein |
| `diakronos_app.api.registrierungslink_api.delete_link` | ['POST'] | nein |
| `diakronos_app.api.registrierungslink_api.toggle_link` | ['POST'] | nein |
| `diakronos_app.api.registrierungslink_api.update_link` | ['POST'] | nein |
| `diakronos_app.api.registrierungslink_api.verlaengern_link` | ['POST'] | nein |
| `diakronos_app.api.ressourcen.create_buchung` | ['POST'] | nein |
| `diakronos_app.api.ressourcen.create_ressource` | ['POST'] | nein |
| `diakronos_app.api.ressourcen.decide_buchung` | ['POST'] | nein |
| `diakronos_app.api.ressourcen.decide_termin_ressource` | ['POST'] | nein |
| `diakronos_app.api.ressourcen.delete_buchung` | ['POST'] | nein |
| `diakronos_app.api.ressourcen.delete_ressource` | ['POST'] | nein |
| `diakronos_app.api.ressourcen.update_buchung` | ['POST'] | nein |
| `diakronos_app.api.ressourcen.update_ressource` | ['POST'] | nein |
| `diakronos_app.api.sicherung.sicherung_einstellungen_speichern` | ['POST'] | nein |
| `diakronos_app.api.sicherung.sicherung_get` | — | nein |
| `diakronos_app.api.sicherung.sicherung_jetzt` | ['POST'] | nein |
| `diakronos_app.api.sicherung.sicherung_loeschen` | ['POST'] | nein |
| `diakronos_app.api.veranstaltungsanmeldung.register_mitglied` | ['POST'] | nein |
| `diakronos_app.api.verantwortliche.set_verantwortliche` | ['POST'] | nein |
| `diakronos_app.api.website.bausteine_installieren` | ['POST'] | nein |
| `diakronos_app.api.website.beitrag_auf_website` | ['POST'] | nein |
| `diakronos_app.api.website.freigabe_setzen` | ['POST'] | nein |
| `diakronos_app.api.website.freigaben_lesen` | — | nein |
| `diakronos_app.api.website.kategorie_oeffentlich` | ['POST'] | nein |
| `diakronos_app.api.website.login_uebergabe` | ['POST'] | nein |
| `diakronos_app.api.website.postfach_loeschen` | ['POST'] | nein |
| `diakronos_app.api.website.postfach_speichern` | ['POST'] | nein |
| `diakronos_app.api.wiki.create_wiki_artikel` | ['POST'] | nein |
| `diakronos_app.api.wiki.delete_wiki_artikel` | ['POST'] | nein |
| `diakronos_app.api.wiki.update_wiki_artikel` | ['POST'] | nein |
| `diakronos_app.api.zugang.einladungslink` | ['POST'] | nein |
| `diakronos_app.api.zugang.konto_anlegen` | ['POST'] | nein |
| `diakronos_app.api.zugang.konto_freischalten` | ['POST'] | nein |
| `diakronos_app.api.zugang.konto_sperren` | ['POST'] | nein |
| `diakronos_app.api.zugang.passwort_uebernehmen` | ['POST'] | ja |
| `diakronos_app.api.zugang.setze_passwort` | ['POST'] | nein |
| `diakronos_app.api.zugang.setze_rollen` | ['POST'] | nein |
| `diakronos_app.devmodus.api.audio_hochladen` | ['POST'] | nein |
| `diakronos_app.devmodus.api.aufraeumen` | ['POST'] | nein |
| `diakronos_app.devmodus.api.befund_loeschen` | ['POST'] | nein |
| `diakronos_app.devmodus.api.befund_setzen` | ['POST'] | nein |
| `diakronos_app.devmodus.api.befund_speichern` | ['POST'] | nein |
| `diakronos_app.devmodus.api.bericht_erzeugen` | ['POST'] | nein |
| `diakronos_app.devmodus.api.bild_hochladen` | ['POST'] | nein |
| `diakronos_app.devmodus.api.sitzung_beenden` | ['POST'] | nein |
| `diakronos_app.devmodus.api.sitzung_starten` | ['POST'] | nein |
| `diakronos_app.website.kontakt.kontakt_senden` | ['POST'] | ja |

## Lesende Funktionen

| Funktion | Methoden | Gast |
|---|---|---|
| `diakronos_app.anmeldung.einstellungen_api.anmeldung_get_rollen` | — | nein |
| `diakronos_app.api.admin_hub.get_anmeldeformular_felder` | — | nein |
| `diakronos_app.api.admin_hub.get_anmeldeformular_kopf` | — | nein |
| `diakronos_app.api.admin_hub.get_anmeldeformulare` | — | nein |
| `diakronos_app.api.admin_hub.get_anmeldungen_hub` | — | nein |
| `diakronos_app.api.admin_hub.get_dsgvo_uebersicht` | — | nein |
| `diakronos_app.api.admin_hub.get_statistik` | — | nein |
| `diakronos_app.api.audit.get_my_audit_log` | — | nein |
| `diakronos_app.api.audit.get_my_notifications` | — | nein |
| `diakronos_app.api.audit.get_unread_notifications` | — | nein |
| `diakronos_app.api.auswahl.get_inhalt_optionen` | — | nein |
| `diakronos_app.api.auswahl.get_kalender_optionen` | — | nein |
| `diakronos_app.api.auswahl.get_ressourcen_optionen` | — | nein |
| `diakronos_app.api.auswahl.get_sammlungen` | — | nein |
| `diakronos_app.api.beitraege.get_beitraege_liste` | — | nein |
| `diakronos_app.api.beitraege.get_beitrag_detail` | — | nein |
| `diakronos_app.api.bugreport.detail` | — | nein |
| `diakronos_app.api.bugreport.liste` | — | nein |
| `diakronos_app.api.dashboard.get_available_widgets` | — | nein |
| `diakronos_app.api.dashboard.get_events_for_month` | — | nein |
| `diakronos_app.api.dashboard.get_meine_buchungen_widget` | — | nein |
| `diakronos_app.api.dashboard.get_moderation_vorschlaege` | — | nein |
| `diakronos_app.api.dashboard.get_navigation_zaehler` | — | nein |
| `diakronos_app.api.dashboard.get_pinned_beitraege` | — | nein |
| `diakronos_app.api.dashboard.get_recent_articles` | — | nein |
| `diakronos_app.api.dashboard.get_upcoming_events` | — | nein |
| `diakronos_app.api.dashboard.get_user_config` | — | nein |
| `diakronos_app.api.dashboard.get_widget_badge_counts` | — | nein |
| `diakronos_app.api.dashboard.get_widget_data` | — | nein |
| `diakronos_app.api.datenschutz.auskunft` | — | nein |
| `diakronos_app.api.datenschutz.get_loeschantraege` | — | nein |
| `diakronos_app.api.datenschutz.mein_loeschantrag` | — | nein |
| `diakronos_app.api.datenschutz.meine_auskunft` | — | nein |
| `diakronos_app.api.dienstplan.get_dienstplan` | — | nein |
| `diakronos_app.api.dienstplan.get_dienstrollen` | — | nein |
| `diakronos_app.api.dienstplan.get_meine_dienste` | — | nein |
| `diakronos_app.api.einrichtung.status` | — | nein |
| `diakronos_app.api.fail_validation` | — | nein |
| `diakronos_app.api.gruppen.get_ankuendigungen` | — | nein |
| `diakronos_app.api.gruppen.get_aufgaben` | — | nein |
| `diakronos_app.api.gruppen.get_gruppe_detail` | — | nein |
| `diakronos_app.api.gruppen.get_gruppe_mitglieder_auswahl` | — | nein |
| `diakronos_app.api.gruppen.get_gruppe_termine` | — | nein |
| `diakronos_app.api.gruppen.get_gruppen_for_orgchart` | — | nein |
| `diakronos_app.api.gruppen.get_gruppen_hierarchie` | — | nein |
| `diakronos_app.api.gruppen.get_gruppen_page_data` | — | nein |
| `diakronos_app.api.gruppen.get_untergruppe_detail` | — | nein |
| `diakronos_app.api.kronos.ablaufplan_api.get_ablaufplan` | — | nein |
| `diakronos_app.api.kronos.ablaufplan_api.get_termine_am_tag` | — | nein |
| `diakronos_app.api.kronos.calendar_get.get_calendar_events` | — | nein |
| `diakronos_app.api.kronos.calendar_get.get_mein_termin` | — | nein |
| `diakronos_app.api.kronos.calendar_get.get_meine_abgelehnten_termine` | — | nein |
| `diakronos_app.api.kronos.event_crud.get_offene_aenderungen` | — | nein |
| `diakronos_app.api.kronos.kalender.get_events` | — | nein |
| `diakronos_app.api.kronos.kalender_verwaltung.get_kalender_verwaltung` | — | nein |
| `diakronos_app.api.kronos.kanban_api.get_conflict_partner` | — | nein |
| `diakronos_app.api.kronos.kanban_api.get_kanban_board_data` | — | nein |
| `diakronos_app.api.kronos.kanban_api.get_moderation_count` | — | nein |
| `diakronos_app.api.kronos.permissions.get_accessible_calendars` | — | nein |
| `diakronos_app.api.kronos.permissions.get_accessible_modules` | — | nein |
| `diakronos_app.api.kronos.permissions.get_session_info` | — | nein |
| `diakronos_app.api.kronos.permissions.get_writable_calendars` | — | nein |
| `diakronos_app.api.kronos.ressource_api.check_resource_conflict` | — | nein |
| `diakronos_app.api.kronos.ressource_api.get_conflict_events` | — | nein |
| `diakronos_app.api.kronos.ressource_api.get_kronos_settings` | — | nein |
| `diakronos_app.api.kronos.ressource_api.get_ressources` | — | nein |
| `diakronos_app.api.mailversand.mailversand_get` | — | nein |
| `diakronos_app.api.mailversand.mailversand_status` | — | nein |
| `diakronos_app.api.mitglieder.exportiere_mitglieder_csv` | — | nein |
| `diakronos_app.api.mitglieder.get_adressbuch` | — | nein |
| `diakronos_app.api.mitglieder.get_beziehungen_for_mitglied` | — | nein |
| `diakronos_app.api.mitglieder.get_gruppen_for_mitglied` | — | nein |
| `diakronos_app.api.mitglieder.get_mitglied_detail` | — | nein |
| `diakronos_app.api.mitglieder.get_mitglieder_liste` | — | nein |
| `diakronos_app.api.mitglieder.pruefe_mitglied_dublette` | — | nein |
| `diakronos_app.api.orgchart_api.get_orgchart_data` | — | nein |
| `diakronos_app.api.ping` | — | nein |
| `diakronos_app.api.planrahmen.abwesenheiten_liste` | — | nein |
| `diakronos_app.api.planrahmen.bedarf` | — | nein |
| `diakronos_app.api.planrahmen.doku_holen` | — | nein |
| `diakronos_app.api.planrahmen.einrichten_rechte` | — | nein |
| `diakronos_app.api.planrahmen.feiertage_holen` | — | nein |
| `diakronos_app.api.planrahmen.feld_kandidaten` | — | nein |
| `diakronos_app.api.planrahmen.kochbuch_holen` | — | nein |
| `diakronos_app.api.planrahmen.kochbuch_liste` | — | nein |
| `diakronos_app.api.planrahmen.lied_rechte` | — | nein |
| `diakronos_app.api.planrahmen.meine_dienste` | — | nein |
| `diakronos_app.api.planrahmen.merkmal_kandidaten` | — | nein |
| `diakronos_app.api.planrahmen.plaene_liste` | — | nein |
| `diakronos_app.api.planrahmen.plan_holen` | — | nein |
| `diakronos_app.api.planrahmen.plan_stand_version` | — | nein |
| `diakronos_app.api.planrahmen.plantyp_auswirkung` | — | nein |
| `diakronos_app.api.planrahmen.plantyp_pruefen` | — | nein |
| `diakronos_app.api.planrahmen.plantyp_versionen_liste` | — | nein |
| `diakronos_app.api.planrahmen.plantypen_liste` | — | nein |
| `diakronos_app.api.planrahmen.schema_holen` | — | nein |
| `diakronos_app.api.planrahmen.stammdaten_holen` | — | nein |
| `diakronos_app.api.planrahmen.termin_struktur` | — | nein |
| `diakronos_app.api.planrahmen.termin_strukturen` | — | nein |
| `diakronos_app.api.planrahmen.trockenlauf` | — | nein |
| `diakronos_app.api.planung.get_abgeleitete_positionen` | — | nein |
| `diakronos_app.api.planung.get_besetzungsmatrix` | — | nein |
| `diakronos_app.api.planung.get_plaene` | — | nein |
| `diakronos_app.api.planung.get_plan_uebersicht` | — | nein |
| `diakronos_app.api.planung.get_positionen` | — | nein |
| `diakronos_app.api.planung.get_teilnehmer` | — | nein |
| `diakronos_app.api.planung.get_vorlagen` | — | nein |
| `diakronos_app.api.profile.get_my_profile` | — | nein |
| `diakronos_app.api.psalmos.musik.get_fassungen` | — | nein |
| `diakronos_app.api.psalmos.musik.get_lied_detail` | — | nein |
| `diakronos_app.api.psalmos.musik.get_lied_filteroptionen` | — | nein |
| `diakronos_app.api.psalmos.musik.get_lied_historie` | — | nein |
| `diakronos_app.api.psalmos.musik.get_lieder` | — | nein |
| `diakronos_app.api.psalmos.musik.get_liedgruppe_detail` | — | nein |
| `diakronos_app.api.psalmos.musik.get_liedgruppen` | — | nein |
| `diakronos_app.api.registrierung.get_oeffentliche_formular` | — | ja |
| `diakronos_app.api.registrierung.validate_token` | — | ja |
| `diakronos_app.api.registrierung_vorschau.get_formular_vorschau` | — | nein |
| `diakronos_app.api.ressourcen.check_verfuegbarkeit` | — | nein |
| `diakronos_app.api.ressourcen.get_anfragen` | — | nein |
| `diakronos_app.api.ressourcen.get_meine_buchungen` | — | nein |
| `diakronos_app.api.ressourcen.get_ressource_buchungen` | — | nein |
| `diakronos_app.api.ressourcen.get_ressourcen_liste` | — | nein |
| `diakronos_app.api.ressourcen.get_ressourcen_verwaltung` | — | nein |
| `diakronos_app.api.session.check_permission` | — | nein |
| `diakronos_app.api.session.get_current_user_context` | — | nein |
| `diakronos_app.api.session.get_mitglied_permissions` | — | nein |
| `diakronos_app.api.session.sitzung_status` | — | nein |
| `diakronos_app.api.veranstaltungsanmeldung.check_anmeldestatus` | — | nein |
| `diakronos_app.api.verantwortliche.get_verantwortliche` | — | nein |
| `diakronos_app.api.verantwortliche.get_verantwortliche_auswahl` | — | nein |
| `diakronos_app.api.verantwortliche.get_zugangs_rollen` | — | nein |
| `diakronos_app.api.website.bausteine_status` | — | nein |
| `diakronos_app.api.website.rollen` | — | nein |
| `diakronos_app.api.website.status` | — | nein |
| `diakronos_app.api.wiki.get_wiki_artikel_detail` | — | nein |
| `diakronos_app.api.wiki.get_wiki_artikel_liste` | — | nein |
| `diakronos_app.api.wiki.get_wiki_kategorien` | — | nein |
| `diakronos_app.api.wiki.get_wiki_tags` | — | nein |
| `diakronos_app.api.zugang.get_konten_liste` | — | nein |
| `diakronos_app.api.zugang.get_moderator_auswahl` | — | nein |
| `diakronos_app.api.zugang.get_rollen_uebersicht` | — | nein |
| `diakronos_app.api.zugang.get_wartende_konten` | — | nein |
| `diakronos_app.api.zugang.get_zugang` | — | nein |
| `diakronos_app.api.zugang.get_zugangsmodus` | — | nein |
| `diakronos_app.devmodus.api.befund_holen` | — | nein |
| `diakronos_app.devmodus.api.befunde_holen` | — | nein |
| `diakronos_app.devmodus.api.bild` | — | nein |
| `diakronos_app.devmodus.api.ereignisse_holen` | — | nein |
| `diakronos_app.devmodus.api.sitzung_status` | — | nein |
| `diakronos_app.devmodus.api.uebersicht` | — | nein |
| `diakronos_app.website.kontakt.postfaecher_oeffentlich` | ['GET'] | ja |
| `diakronos_app.website.oeffentlich_api.beitraege` | ['GET'] | ja |
| `diakronos_app.website.oeffentlich_api.gruppe` | ['GET'] | ja |
| `diakronos_app.website.oeffentlich_api.gruppen` | ['GET'] | ja |
| `diakronos_app.website.oeffentlich_api.kalender` | ['GET'] | ja |
| `diakronos_app.website.oeffentlich_api.naechster_termin` | ['GET'] | ja |
| `diakronos_app.website.oeffentlich_api.termine` | ['GET'] | ja |
