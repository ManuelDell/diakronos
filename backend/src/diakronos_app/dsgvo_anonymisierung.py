"""Vollständige Anonymisierung einer Person auf Antrag (DSGVO-1, D5).

WOZU EIN EIGENES MODUL
----------------------
Die N6-Fassung (`api/datenschutz.py::anonymisieren`) hat den Personenstamm, die
Registrierungen und das Konto bereinigt. Das reicht für Art. 17 nicht: Freitext-
nennungen in Beiträgen, Fehlerberichten, Audit-Protokollen, Benachrichtigungen,
Plan-Snapshots, OIDC-Zuordnungen und Kalender-Abos trugen den Namen weiter.
Diese Karte (Fachentscheidung Manuel 2026-10-20) verlangt:

    „danach wird VOLLSTÄNDIG anonymisiert: keine Mail mehr da, kein Name mehr
     da, nichts Personenbezogenes. NICHT rückgängig zu machen.“

NEUTRALE KENNUNG STATT KLARNAME (K1, R-DSGVO-1)
-----------------------------------------------
Im Betrieb ist `mitglied.name` der KLARNAME („Hans Beispiel“), nicht eine
technische Kennung. Ein Leeren der Stammdaten hätte den Namen deshalb als
Primärschlüssel stehen lassen — samt jeder Zeile, die darauf verweist
(`loeschantrag.mitglied`, `audit_log.target_name`, Plan-Einträge …).
Der Löschvorgang vergibt darum eine NEUE neutrale Kennung `geloescht-<hex>`,
hängt alle Verweise innerhalb derselben Transaktion um und löscht die alte
Zeile. Welche Spalten Verweise sind, steht NICHT in einer Handliste: es wird
aus den SQLAlchemy-Metadaten abgeleitet (jede Fremdschlüssel-Spalte auf
`mitglied.name` bzw. `user.name`). `tests/test_dsgvo1_inventar.py` prüft gegen
`pg_constraint`, dass keine FK unversorgt bleibt.

SPALTEN OHNE FREMDschlÜSSEL
---------------------------
`ablaufplan_position.verantwortlicher`, `pr_merkmal_wert.ziel_id`, die
JSON-Spalten des Planrahmens (`pr_eintrag.wert`, `pr_verlauf.vorher/nachher`,
`pr_plan.veroeffentlichter_stand`, `dm_befund.*`) und die Namensspalten
`ressourcen_buchung.gebucht_von(_name)` tragen Mitglied-Kennungen als WERT.
Sie werden gezielt und EXAKT umgeschrieben (ganzer Wert bzw. JSON-Wert gleich
der alten Kennung) — nicht per Teilstring-Suche.

KEINE BLINDE FREITEXT-ERSETZUNG (K2)
------------------------------------
Die frühere Fassung ersetzte die Werte der Person als TEILSTRING über alle
Textspalten aller Tabellen. Das beschädigte fremde Daten: „Stuttgart“ wurde bei
neun anderen Mitgliedern zu `[gelöscht]`, eine fremde Notiz verlor die
Groß-/Kleinschreibung und „Hans-Peter“ wurde zerstört. Jetzt gilt:

* **Eigene Zeilen** (eigene Felder, eigene Protokolle, eigene Anmeldungen,
  eigene Benachrichtigungen, eigene Einwilligungen) werden gezielt geleert,
  gelöscht oder neutral gesetzt.
* **Fremde Texte** werden NUR angefasst, wenn der VOLLE Name („Vorname
  Nachname“, „Nachname, Vorname“), die Mail-Adresse oder die Telefonnummer als
  GANZES WORT dasteht (Wortgrenzen, Groß/klein egal, Originalschreibung des
  übrigen Textes bleibt). Wohnort, PLZ, Straße und einzelne Vornamen bleiben in
  fremden Texten stehen — „Eva“ trifft sonst „Evangelisch“, „Ben“ trifft
  „Benutzer“.

REIHENFOLGE (K3, verbindlich)
-----------------------------
Die Anonymisierung läuft in der Transaktion des Aufrufers und wird VOR dem
Mailversand geflusht — alle FK-/Constraint-Fehler treten dabei auf. Erst danach
geht die Mail raus; scheitert sie, rollt der Aufrufer zurück (nichts gelöscht,
erneut versuchbar). Dieses Modul sendet nicht.

WAS BEWUSST NICHT ANGEFASST WIRD
--------------------------------
* `user.name` ist die E-Mail und der Primärschlüssel: die Konto-Zeile wird
  GELÖSCHT (nicht anonymisiert). Vorher werden alle Verweise darauf aufgelöst.
* Redis: Sitzungen werden widerrufen (`widerrufe_sitzungen`), der Status-Cache
  vergessen (`vergiss`). Schlüssel enthalten keine Namen (Hash, s.
  `benutzer_status._pseudonym`) — geprüft in `test_dsgvo1_anonymisierung.py`.
* Dateien: Profilbild und persönliche Anhänge werden physisch entfernt
  (`dateien_entfernen`), nachdem die Transaktion committet ist.

KENNUNG STATT KLARNAME (ID-1f)

`mitglied.name` war im Betrieb der Klarname; ID-1 hat ihn auf eine zufällige
Kennung umgeschlüsselt und die alte Form in `id1_mitglied_kennung`
(`alt` -> `neu`) abgelegt. Ohne eigenen Schritt wäre diese Tabelle die letzte
Stelle, an der der Klarname einer gelöschten Person stünde — samt Einwilligungs-
Schlüsseln wie `DSGVO-<Klarname>-0002`. Deshalb:

* `id1_mitglied_kennung`: die Zeile(n) der Person werden GELÖSCHT — über die
  AKTUELLE Kennung UND über jede frühere Kennung (`alt`), die über `neu` zur
  Person gehört (transitive Hülle). Die Tabelle ist ein Umzugsprotokoll, kein
  Nachweis; `alt` und `neu` werden daher nicht umgeschrieben, sondern fallen mit
  der Zeile (`ZEILEN_LOESCHEN`).
* `dsgvo_einwilligung.name`: der Schlüssel EIGENER Zeilen wird auf die neutrale
  Kennung umgeschrieben — zweistufig: ZUERST die Bauform `DSGVO-<Kennung>-<n>`
  bzw. `EINW-<Kennung>-<n>` (dieselbe Musterregel wie in der Migration
  `id1_mitglied_kennungen._einwilligung_neu`), auch wenn der Namensanteil noch
  eine FRÜHERE Kennung der Person ist; DANACH die Klarnamen-Suche von vor ID-1
  für alles, was diese Bauform nicht trifft (`DSGVO-<Name>-0114-1`,
  Altzeilen ohne Abbildungs-Eintrag). Die laufende Nummer bleibt. Fremde Zeilen
  bleiben zeichengleich — auch namensgleiche (Art. 7 des Dritten).

Beides ist bestandsfest: existiert `id1_mitglied_kennung` nicht (Downgrade,
ältere Test-DB), läuft die Löschung unverändert durch.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4

from sqlalchemy import String, Text, and_, delete, or_, select, update

#: Platzhalter-Konto für Verweise, die eine Fachaussage tragen. Kein Login
#: möglich: die Zeile wird nie angelegt (`enabled` ist überall falsch, kein
#: Passwort, keine Rolle).
GELOESCHTES_KONTO = "geloeschte-person@deleted.invalid"

#: Präfix der neuen neutralen Mitglied-Kennung (`geloescht-<hex>`). Sie ist
#: bewusst KEIN Name und keine Adresse — nur eine technische Kennung, an der
#: Nachweis (Löschantrag, Einwilligung, Protokoll) und Planhistorie hängen.
GELOESCHT_PRAEFIX = "geloescht-"

#: Umzugsprotokoll der Kennungen aus der Migration ID-1 (`alt` -> `neu`,
#: `alembic/versions/id1_mitglied_kennungen.py`). Die Tabelle ist KEIN Nachweis:
#: die Zeilen der gelöschten Person werden entfernt (`_zeilen_loeschen`).
#: Existiert sie nicht (Downgrade, ältere DB), läuft die Löschung ohne sie.
KENNUNG_ABBILDUNG = "id1_mitglied_kennung"

#: Präfixe der Nachweis-Schlüssel (`frappe_compat/api_helpers._new_name` legt
#: `DSGVO-<Kennung>-<n>` an; Altbestand nutzt auch `EINW-<Kennung>-<n>`).
#: Dieselbe Liste führt die Migration (`EINWILLIGUNG_SPALTEN`).
EINWILLIGUNG_PRAEFIXE = ("DSGVO-", "EINW-")

VORNAME = "Gelöschte"
NACHNAME = "Person"
ANZEIGENAME = f"{VORNAME} {NACHNAME}"

#: Ersatz für Werte der Person in FREMDEN Texten (nur volle Nennungen, s.
#: `_fremdtexte_ersetzen`). Bewusst nicht leer: ein leerer Platz sieht aus wie
#: „nie ausgefüllt“, der Platzhalter sagt, dass etwas entfernt wurde.
FREITEXT_ERSETZUNG = "[gelöscht]"

#: Reihenfolge der Mitglied-Spalten in der NEUEN Zeile (POSITIVLISTE).
#: Übernommen werden NUR technische Felder: Anlage-/Änderungszeit und
#: -konto, `docstatus`, `idx`. ALLES andere — jeder Name, jede Adresse, jeder
#: Freitext und jede künftige Spalte (etwa `austritt_grund`, `austritt_datum`,
#: `vor_austritt_status`, `vor_austritt_konto_aktiv`) — wird NICHT übernommen.
#:
#: Die Liste stand vorher als AUSSCHLUSSLISTE (`_MITGLIED_LEER`): eine neue
#: Spalte war damit automatisch in der anonymisierten Zeile — genau der Weg,
#: auf dem der Austritt seinen Freitext („Umzug nach …“) und die Kontenliste
#: in die gelöschte Zeile getragen hätte.
_MITGLIED_TECHNISCH = (
    "creation", "modified", "owner", "modified_by", "docstatus", "idx",
)
_MITGLIED_LEER = _MITGLIED_TECHNISCH  # Altname (Doku/Tests)


@dataclass
class Bestand:
    """Alles, was die Person identifiziert — VOR dem ersten Schreibzugriff.

    Ohne diese Liste ließe sich die Vollständigkeit nicht prüfen: nach dem
    ersten UPDATE steht der Name nicht mehr in `mitglied`, und eine Suche nach
    ihm fände nichts (auch nicht im Test).
    """

    mitglied: str
    konten: set[str] = field(default_factory=set)
    #: Volle Namen in beiden Schreibweisen („Anna Muster“, „Muster, Anna“).
    #: NUR Namen aus mindestens zwei Teilen (N-1, R-DSGVO-1b): ein einzelner
    #: Nachname wie „Muster“ steht auch in fremden Daten („Anna Muster“) und
    #: würde dort zerstört.
    namen: set[str] = field(default_factory=set)
    #: Einzelne Namensteile (nur EIN Name vorhanden, einteiliges Konto). Sie
    #: bleiben im Suchwert des Nachweises, werden aber NICHT in fremden Texten
    #: ersetzt (N-1: „Hat eine Person nur einen Namensteil, wird dieser in
    #: fremden Texten nicht gesucht“).
    namensteile: set[str] = field(default_factory=set)
    adressen: set[str] = field(default_factory=set)
    telefon: set[str] = field(default_factory=set)
    anmeldungen: set[str] = field(default_factory=set)
    dateien: set[str] = field(default_factory=set)
    #: Texte, die die Person selbst ausgelöst hat (Benachrichtigung an die
    #: Verwaltung, Fehlerberichte …). Sie enthalten den Namen als Fließtext,
    #: nicht als Wert einer Spalte.
    meldungen: set[str] = field(default_factory=set)
    #: Wohnort, Straße, Hausnummer, PLZ, Geburtstag: Werte der Person, die NUR
    #: in ihrer eigenen Zeile stehen. In fremden Texten bleiben sie stehen
    #: (Fachentscheidung, s. `_fremdtexte_ersetzen`).
    orte: set[str] = field(default_factory=set)
    #: FRÜHERE Kennungen der Person (ID-1f): vor dem Umschlüsseln (ID-1) hieß
    #: `mitglied.name` im Betrieb der Klarname; die Migration legt diese Form in
    #: `id1_mitglied_kennung` ab. Einwilligungs-Schlüssel aus der Zeit davor
    #: tragen sie noch (`DSGVO-<frühere Kennung>-0002`).
    kennungen: set[str] = field(default_factory=set)

    @property
    def suchwerte(self) -> list[str]:
        """Alles, was die Person identifizierbar macht — die Prüfliste des
        Vollscans. Telefon zusätzlich als reine Ziffernfolge („0170 4455667“
        wird auch „01704455667“ geschrieben)."""
        # Auch Konto-Kennungen: eine Adresse ohne `mitglied`-Zeile (Antrag über
        # die Oberfläche, Konto von Hand angelegt) steht NUR in `user.name` und
        # `has_role.parent` — ohne diesen Zusatz bleibt sie als Rest stehen.
        werte = {
            w.strip()
            for w in (self.namen | self.namensteile | self.adressen
                      | self.telefon | self.meldungen | self.konten)
            if str(w).strip()
        }
        for nummer in self.telefon:
            ziffern = "".join(z for z in str(nummer) if z.isdigit())
            if len(ziffern) >= 6:
                werte.add(ziffern)
        return sorted(werte, key=len, reverse=True)

    @property
    def fremd_nadeln(self) -> list[str]:
        """Nur die Werte, die in FREMDEN Texten als ganzes Wort ersetzt werden
        (Fachentscheidung K2): VOLLE Namen (ab zwei Teilen), Adressen,
        Telefonnummern — keine Orte und NIE ein einzelner Namensteil (N-1)."""
        werte = {
            w.strip()
            for w in (self.namen | self.adressen | self.telefon)
            if str(w).strip()
        }
        for nummer in self.telefon:
            ziffern = "".join(z for z in str(nummer) if z.isdigit())
            if len(ziffern) >= 6:
                werte.add(ziffern)
        return sorted(werte, key=len, reverse=True)


# ── Das Inventar ────────────────────────────────────────────────────────────
#
# Quellen: `pg_constraint` der constraint-identischen Kopie, `models/*.py` und
# die Textspalten der Betriebs-DB (`information_schema.columns`).
#
# FREMDschlÜSSEL werden NICHT hier gepflegt — sie werden zur Laufzeit aus den
# Metadaten abgeleitet (`verweise()`), damit eine neue FK nicht still durch-
# rutscht. Dieses Inventar sagt nur, WAS mit dem Wert geschieht:
#
#   "mitglied"      FK/Verweis auf die Person: auf die NEUE Kennung umhängen
#   "mitglied_null" FK auf die Person, die geleert wird (Selbstbezug)
#   "user_null"     FK/Verweis auf das Konto: NULLen
#   "user_platzhalter"  NOT NULL oder Fachaussage: auf GELOESCHTES_KONTO
#   "eigene_datei"  Datei-Verweis der Person: Zeile weg, Datei physisch löschen
#   "keep"          Nachweis (Art. 17/7): Zeile bleibt, Bezug ist die Kennung
#   "eigene_kennung" Schlüssel einer eigenen Zeile trägt die Kennung der Person:
#                   auf die neutrale Kennung umschreiben (ID-1f). Steht auch bei
#                   `id1_mitglied_kennung`, dort aber nur als Entscheidung — die
#                   Zeile fällt (s. `ZEILEN_LOESCHEN`), umgeschrieben wird nichts.
#   "protokoll"     Spalte der Person, deren Text die Person nennen kann
#   "fremd"         Spalte ANDERER Zeilen, in der die Person nur als Text steht
#
# TABELLEN, DEREN ZEILEN GANZ VERSCHWINDEN, stehen in `ZEILEN_LOESCHEN`; dort
# wird vorher nichts genullt (die Zeile ist ohnehin weg).

SPALTEN: dict[str, dict[str, tuple[str, str]]] = {
    "anmeldung": {
        "mitglied": ("mitglied", "Veranstaltungs-/Kursanmeldung: Zeile bleibt, Zuordnung weg"),
        "vorname": ("protokoll", "Name der anmeldenden Person"),
        "nachname": ("protokoll", "Name der anmeldenden Person"),
        "email": ("protokoll", "Adresse der Person"),
        "email_freitext": ("protokoll", "Adresse als Freitext"),
        "name_freitext": ("protokoll", "Name als Freitext"),
        "telefon": ("protokoll", "Telefon der Person"),
        "kommentar": ("protokoll", "Freitextkommentar der Person"),
        "ip_adresse": ("protokoll", "IP der Anmeldung"),
    },
    "audit_log": {
        "actor": ("user_null", "wer gehandelt hat: Protokoll bleibt, Konto weg"),
        "target_user": ("user_null", "Ziel-Konto eines Eingriffs"),
        # Nach der Umhängung steht hier die NEUE Kennung — kein Name mehr.
        "target_name": ("keep", "Ziel-Objekt; bei DocType Mitglied die Kennung"),
        "old_value": ("protokoll", "alter Wert der Person -> Platzhalter"),
        "new_value": ("protokoll", "neuer Wert der Person -> Platzhalter"),
        "confirm_reason": ("protokoll", "Freitext zur Bestätigung"),
        "begruendung": ("protokoll", "Begründung eines Eingriffs"),
        "error_message": ("protokoll", "Fehlertext kann Werte enthalten"),
        "ip_address": ("protokoll", "IP des Vorgangs"),
        "user_agent": ("protokoll", "Browserkennung des Vorgangs"),
    },
    "beitrag": {
        "autor": ("protokoll", "Autorenname eines Beitrags"),
        "autor_email": ("protokoll", "Autorenadresse eines Beitrags"),
        "inhalt": ("protokoll", "Freitext kann die Person nennen"),
    },
    "beitrag_kommentar": {
        "autor": ("protokoll", "Autorenname eines Kommentars"),
        "autor_email": ("protokoll", "Autorenadresse eines Kommentars"),
        "text": ("protokoll", "Freitext kann die Person nennen"),
    },
    "wiki_artikel": {
        "autor": ("protokoll", "Autorenname"),
        "autor_email": ("protokoll", "Autorenadresse"),
        "inhalt": ("protokoll", "Freitext kann die Person nennen"),
    },
    "bug_report": {
        "mitglied": ("mitglied", "Fehlerbericht der Person"),
        "benutzer": ("user_null", "Konto des Melders"),
        "beschreibung": ("protokoll", "Freitext des Melders"),
        "notiz": ("protokoll", "Freitext des Melders"),
        "konsole_log": ("protokoll", "Browser-Log kann Werte enthalten"),
        "netzwerk_log": ("protokoll", "Netzwerk-Log kann Adressen enthalten"),
        "element_html": ("protokoll", "DOM-Auszug kann Namen enthalten"),
        "element_text": ("protokoll", "sichtbarer Text kann Namen enthalten"),
        "url": ("protokoll", "URL kann Suchbegriffe/IDs enthalten"),
        "user_agent": ("protokoll", "Browserkennung"),
        "screenshot": ("eigene_datei", "Bildschirmfoto der Person"),
    },
    "dm_befund": {
        "benutzer": ("user_null", "Dev-Modus-Befund (Zeile wird gelöscht)"),
        "text": ("protokoll", "Befundtext kann Namen enthalten"),
        "url": ("protokoll", "URL des Befunds"),
    },
    "dm_ereignis": {
        "benutzer": ("user_null", "Dev-Modus-Ereignis (Zeile wird gelöscht)"),
        "meldung": ("protokoll", "Fehlertext kann Werte enthalten"),
        "traceback": ("protokoll", "Traceback kann Werte enthalten"),
        "pfad": ("protokoll", "Pfad kann IDs enthalten"),
    },
    "dm_sitzung": {"benutzer": ("user_null", "Dev-Modus-Sitzung (Zeile wird gelöscht)")},
    "dienstplan": {
        "leitung": ("mitglied", "Plan bleibt, Leitung wird frei"),
        "plantitel": ("protokoll", "Plantitel kann Namen enthalten"),
    },
    "dienstplan_mitwirkender": {"mitglied": ("mitglied", "Mitwirkenden-Zeile")},
    "dienstplan_position": {"verantwortlicher": ("mitglied", "Positionsverantwortung")},
    "dienstplan_position_mitglied": {"mitglied": ("mitglied", "Positionsmitglied")},
    "dienstplan_teilnehmer": {
        "mitglied": ("mitglied", "Einplanung"),
        "kontakt_abweichend": ("mitglied", "abweichender Kontakt verweist auf eine Person"),
        "notiz_intern": ("protokoll", "interne Notiz zur Person"),
    },
    "element_mitarbeiter": {
        "mitglied": ("mitglied", "Mitarbeiter eines Kalender-Elements"),
        "notiz": ("protokoll", "Notiz zur Person"),
    },
    "gruppenmitgliedschaft": {
        "mitglied": ("mitglied", "Gruppenmitgliedschaft"),
        "notiz": ("protokoll", "Notiz zur Person"),
    },
    "untergruppenmitgliedschaft": {
        "mitglied": ("mitglied", "Untergruppenmitgliedschaft"),
        "notiz": ("protokoll", "Notiz zur Person"),
    },
    "ablaufplan_position": {
        "verantwortlicher": ("mitglied", "Positionsverantwortung im Ablaufplan"),
    },
    "gruppen_ankuendigung": {"erstellt_von": ("mitglied", "Autor einer Ankündigung")},
    "gruppen_aufgabe": {"erstellt_von": ("mitglied", "Ersteller einer Aufgabe")},
    "mitglied": {
        # Selbstbezüge: Zeigen sie auf die Person, werden sie geleert (ihre
        # Gegenrichtung zeigt nach der Umhängung auf die neue Kennung).
        "ehepartner": ("mitglied_null", "Selbstbezug Ehepartner"),
        "elternteil": ("mitglied_null", "Selbstbezug Elternteil"),
        "user": ("user_null", "Konto-Link des Mitglieds (Konto wird gelöscht)"),
        # Identität der Person: gesetzt von `_mitglied_werte()` in der NEUEN
        # Zeile (die alte fällt). Kontakt/Adresse NULL, Name „Gelöschte Person“.
        "vorname": ("mitglied_werte", "Vorname -> „Gelöschte“"),
        "nachname": ("mitglied_werte", "Nachname -> „Person“"),
        "email": ("mitglied_werte", "Adresse -> NULL (D6: wieder vergebbar)"),
        "telefonnummer": ("mitglied_werte", "Telefon -> NULL"),
        "postleitzahl": ("mitglied_werte", "Adresse -> NULL"),
        "wohnort": ("mitglied_werte", "Adresse -> NULL"),
        "straße": ("mitglied_werte", "Adresse -> NULL"),
        "nummer": ("mitglied_werte", "Adresse -> NULL"),
        "notiz": ("mitglied_werte", "Notiz -> NULL"),
        "foto": ("mitglied_werte", "Profilbild -> NULL (Datei wird gelöscht)"),
        "ancestor_path": ("mitglied_werte", "Anzeigename-Pfad -> NULL"),
        "geschlecht": ("mitglied_werte", "-> NULL"),
        "familienstand": ("mitglied_werte", "-> NULL"),
        "adressbuch_sichtbarkeit": ("mitglied_werte", "-> „{}“"),
        "status": ("mitglied_werte", "Endstatus „geloescht“"),
        # Austritt (AUSTRITT-Merge, Folge B): der Grund ist Freitext der Person
        # („Umzug nach …“) und darf in der anonymisierten Zeile nicht stehen.
        # `_neue_zeile` übernimmt ohnehin nur technische Felder — der Eintrag
        # hier ist die Entscheidung, die der Inventar-Test verlangt.
        "austritt_grund": ("mitglied_werte", "Austrittsgrund (Freitext) -> NULL"),
        # Die Datums-/Zahlspalten (`geburtstag`, `mitglied_seit`, `*_datum`,
        # `auf_bemerkung_gesetzt_seit`) stehen NICHT hier: das Inventar prüft
        # Textspalten (`test_jede_textspalte_hat_eine_entscheidung`), und für
        # sie gilt dieselbe Regel wie für die übrigen Identitätsspalten —
        # `_mitglied_werte()` setzt sie in der neuen Zeile auf NULL.
    },
    "user": {
        # Die Konto-Zeile wird GELÖSCHT (name = Mail = Primärschlüssel, D5).
        "email": ("zeile_loeschen", "Konto-Zeile wird gelöscht"),
        "full_name": ("zeile_loeschen", "Konto-Zeile wird gelöscht"),
        "user_image": ("zeile_loeschen", "Konto-Zeile wird gelöscht"),
        "password_hash": ("zeile_loeschen", "Konto-Zeile wird gelöscht"),
    },
    "mitglied_beziehung": {
        "beziehung_zu": ("mitglied", "Gegenrichtung der Beziehung (Zeile wird gelöscht)"),
    },
    "rollenbesetzung": {
        "teilnehmer": ("mitglied", "Besetzte Rolle in einem Dienstplan"),
        "zugeteilt_von": ("mitglied", "Zuteilung durch die Person"),
        "notiz": ("protokoll", "Notiz zur Person"),
    },
    "sicherer_anhang": {
        "mitglied": ("mitglied", "Anhang mit Sichtbarkeitsstufe (Zeile wird gelöscht)"),
        "datei": ("eigene_datei", "Datei der Person: Zeile weg, Datei gelöscht"),
        "dateiname": ("protokoll", "Dateiname kann Namen enthalten (Zeile wird gelöscht)"),
    },
    "sicherungseinstellungen": {
        # BACKUP-1: die eingestellte Uhrzeit beschreibt den LAUF, nicht eine
        # Person. Der Eintrag ist die Entscheidung, die das Inventar verlangt.
        "uhrzeit": ("struktur", "eingestellte Uhrzeit der Sicherung"),
    },
    "sicherungslauf": {
        # BACKUP-1: Protokoll des Laufs. `ausloeser` („automatisch“/„manuell“)
        # und `meldung` (Fehlertext) beschreiben die Sicherung, nicht die
        # Person; `benachrichtigt` ist die KOMMA-LISTE der benachrichtigten
        # Konto-Adressen — daraus wird der Eintrag der Person EXAKT entfernt
        # (`_konto_listen_bereinigen`), die übrigen bleiben byte-gleich.
        "ausloeser": ("struktur", "Auslöser des Laufs (automatisch/manuell)"),
        "meldung": ("fremd", "Fehlertext des Laufs: kann eine Adresse nennen"),
        "benachrichtigt": ("liste", "Konto-Adressen: Eintrag der Person wird entfernt"),
    },
    "dsgvo_einwilligung": {
        "mitglied": ("keep", "Einwilligungs-Nachweis (Art. 7): Zeile bleibt, Bezug ist die Kennung"),
        # ID-1f: Der SCHLÜSSEL ist die Bauform `DSGVO-<Kennung>-<n>`/`EINW-…`
        # (`frappe_compat/api_helpers._new_name`). Er wird nicht geleert, sondern
        # auf die neutrale Kennung umgeschrieben (`_eigene_schluessel_ersetzen`)
        # — auch aus einer FRÜHEREN Kennung der Person heraus (ID-1). Nur EIGENE
        # Zeilen (`mitglied` = Kennung der Person oder gar keine): der Nachweis
        # eines namensgleichen Dritten bleibt zeichengleich (Art. 7).
        "name": ("eigene_kennung", "Nachweis-Schlüssel trägt die Kennung der Person"),
        "ip_adresse": ("protokoll", "IP der Person (M3: vollständig heißt vollständig)"),
        "user_agent": ("protokoll", "Browserkennung der Person"),
        "quelle": ("protokoll", "Herkunft der Einwilligung"),
    },
    # ID-1f: Umzugsprotokoll der Kennungen (`alt` -> `neu`, Migration
    # `id1_mitglied_kennungen`). KEIN Nachweis: die Zeilen der gelöschten Person
    # verschwinden, sonst stünde der Klarname hier dauerhaft (`alt`). Beide
    # Spalten sind WEISEND für die Löschung (über sie wird die Zeile erkannt) —
    # umgeschrieben wird hier nichts, die Entscheidung ist der Zeilenfall
    # (`ZEILEN_LOESCHEN`). Die Art `eigene_kennung` steht, weil der Wächter je
    # Textspalte eine Entscheidung verlangt.
    "id1_mitglied_kennung": {
        "alt": ("eigene_kennung", "frühere (Klarname-)Kennung der Person: Zeile wird gelöscht"),
        "neu": ("eigene_kennung", "aktuelle Kennung der Person: Zeile wird gelöscht"),
    },
    "loeschantrag": {
        "mitglied": ("keep", "Löschantrag IST der Nachweis, Bezug ist die Kennung"),
        # DSGVO-2a: `abgelehnt_von` ist das Konto des ABLEHNENDEN
        # Administrators (Beschäftigtendatum, nicht das Datensubjekt) — wie
        # freigegeben_von/erledigt_von.
        "abgelehnt_von": (
            "keep",
            "Konto des ABLEHNENDEN Administrators (Beschäftigtendatum, nicht das "
            "Datensubjekt) — wie freigegeben_von/erledigt_von",
        ),
        # N2 (R-DSGVO-2a, Nacharbeit): Die Begründung der Ablehnung ist ein
        # Freitext, den die Verwaltung über eine Person geschrieben hat
        # („Frau X ist erkrankt“). Sie darf nach der Löschung nicht stehen
        # bleiben — der Nachweis der Entscheidung ist der STATUS, nicht der
        # Wortlaut. `protokoll` = Text der Person wird geleert
        # (`_eigene_protokolle`, `loeschantrag` ist dort eine eigene Zeile);
        # der Bestätigende leert sie zusätzlich in derselben Transaktion.
        "ablehnung_grund": (
            "protokoll",
            "Freitext der Verwaltung über die Person -> geleert, Nachweis ist der Status",
        ),
    },
    "pr_abwesenheit": {
        "mitglied": ("mitglied", "Abwesenheit (Zeile wird gelöscht)"),
        "grund": ("protokoll", "Freitextgrund der Abwesenheit"),
    },
    "pr_plan": {
        "verantwortlich": ("mitglied", "Planverantwortung"),
        "created_by": ("user_null", "Anlage-Protokoll des Plans"),
        "titel": ("protokoll", "Plantitel kann Namen enthalten"),
    },
    "pr_termin": {"titel": ("protokoll", "Termintitel kann Namen enthalten")},
    "pr_verlauf": {"benutzer": ("user_null", "Verlaufseintrag im Planrahmen")},
    "pr_plantyp_version": {"erstellt_von": ("user_null", "wer eine Plantyp-Fassung erstellt hat")},
    "pr_plantyp": {"created_by": ("user_null", "wer einen Plantyp angelegt hat")},
    "pr_sammlung": {"created_by": ("user_null", "wer eine Sammlung angelegt hat")},
    "pr_merkmal": {"created_by": ("user_null", "wer ein Merkmal angelegt hat")},
    "gruppe": {"leiter": ("protokoll", "Leiter als Freitextname")},
    "notification_log": {
        "for_user": ("user_null", "persönliche Benachrichtigung"),
        "from_user": ("user_null", "Absender einer Benachrichtigung"),
        "subject": ("protokoll", "Betreff kann Namen enthalten"),
        "email_content": ("protokoll", "Inhalt kann Namen enthalten"),
    },
    "file": {
        # `file_url` ist der Ablagepfad; die Datei dahinter wird in
        # `_eigene_dateien` eingesammelt und nach dem Commit gelöscht.
        "file_url": ("eigene_datei", "Datei-Anhang am Mitglied: Datei wird gelöscht"),
        "file_name": ("protokoll", "Dateiname kann Namen enthalten (Datei wird gelöscht)"),
    },
    "ressourcen_buchung": {
        "moderiert_von": ("user_null", "wer die Buchung moderiert hat (FK auf user)"),
        # KEIN FK, aber eine Kennung bzw. ein Name: die Buchung bleibt als
        # Fachvorgang, der Bucher wird neutral (N-2, R-DSGVO-1b).
        "gebucht_von": ("mitglied_platzhalter", "Kennung des Buchers"),
        "gebucht_von_name": ("mitglied_platzhalter", "Anzeigename des Buchers"),
    },
}

#: Spalten, in denen ein AUTOR steht (Name + Adresse) — Beiträge, Kommentare,
#: Wiki (N-2: das Inventar sagt „protokoll“, der frühere Code kannte diese
#: Spalten aber nicht). Sie werden nicht per Teilstring gesucht, sondern über
#: den EXAKTEN Wert der Person: `autor` → neutraler Name, `autor_email` → NULL.
#: Der Inhalt des Beitrags bleibt stehen.
AUTOR_SPALTEN: dict[str, tuple[str, str]] = {
    "beitrag": ("autor", "autor_email"),
    "beitrag_kommentar": ("autor", "autor_email"),
    "wiki_artikel": ("autor", "autor_email"),
}

#: Spalten OHNE Fremdschlüssel, die Mitglied-Kennungen als WERT tragen. Sie
#: werden gezielt und EXAKT umgeschrieben (Vergleich auf den ganzen Wert bzw.
#: den JSON-Wert), nicht per Teilstring-Suche. Schlüssel: Tabelle → Spalte →
#: Art (`wert` = ganze Spalte, `json` = JSON-Pfad/Werte-Vergleich).
WERT_SPALTEN: dict[str, dict[str, str]] = {
    "pr_merkmal_wert": {"ziel_id": "wert"},
    # Planrahmen: `pr_eintrag.wert` ist der Feldwert (String, Zahl, Liste);
    # Personen stehen dort als Zeichenkette der Kennung.
    "pr_eintrag": {"wert": "json"},
    "pr_verlauf": {"vorher": "json", "nachher": "json"},
    "pr_plan": {"veroeffentlichter_stand": "json"},
    "dm_befund": {"fehlerumfeld": "json", "element": "json", "bilder": "json"},
    # Kinderlose Verweise auf die Person (Dokumentname, nicht FK).
    "notification_log": {"document_name": "wert"},
    "audit_log": {"target_name": "wert"},
    "file": {"attached_to_name": "wert"},
    "pr_sammlung_eintrag": {"daten": "json"},
    # BACKUP-1: `", ".join(zugestellt)` — die Adressen der benachrichtigten
    # Konten (sicherung/lauf.py). Kein Einzelwert, sondern eine Liste: der
    # Eintrag der Person wird EXAKT entfernt, die übrigen bleiben byte-gleich
    # (`_konto_listen_bereinigen`).
    "sicherungslauf": {"benachrichtigt": "liste"},
}

#: Tabellen, deren ZEILEN ganz verschwinden: reine Beziehungs-/Zugangsdaten, an
#: denen nichts nachweisbar ist. `mitglied`-Zeilen, Anmeldungen, Dienstpläne,
#: Protokolle und Einwilligungen bleiben ausdrücklich stehen.
ZEILEN_LOESCHEN: tuple[tuple[str, str], ...] = (
    ("has_role", "Rollen sind der Zugang selbst"),
    ("user_role", "Alt-Rollenzeilen des Kontos"),
    ("passwortzugang", "Startpasswort-Link des Kontos"),
    ("auth_oidc_identitaet", "OIDC-Verknüpfung des Kontos"),
    ("auth_zuordnung_ablehnung", "abgelehnte Zuordnung: enthält Mail und Anzeigename"),
    ("mitglied_bereich", "Kindzuordnung Dienstbereiche"),
    # Fachentscheidung N7 (R-DSGVO-1): Beziehungen ANDERER zur gelöschten
    # Person verschwinden ganz — main hat die Zeile gelöscht, nicht den Verweis
    # genullt; eine Beziehung zu einer nicht mehr existierenden Person ist kein
    # Fachdatum. Die Zeilen der Person selbst fallen mit `parent`.
    ("mitglied_beziehung", "Kindzuordnung Beziehungen (beide Richtungen)"),
    ("anmeldung_antwort", "Freitextantworten der Anmeldung"),
    ("anmeldung_kind", "Angehörige/Kinder der Anmeldung"),
    ("pr_abwesenheit", "Abwesenheit der Person (Grund ist Freitext)"),
    ("user_notification_preference", "Benachrichtigungseinstellung des Kontos"),
    ("dashboard_widget_user_config", "Widget-Anordnung des Kontos"),
    ("nutzereinzelrechte", "Einzelrechte des Kontos"),
    ("kalender_moderator", "Kalender-Moderation des Kontos"),
    ("gruppe_verantwortlicher", "Verantwortlichkeiten des Kontos"),
    ("untergruppe_verantwortlicher", "Verantwortlichkeiten des Kontos"),
    ("dienstbereich_verantwortlicher", "Verantwortlichkeiten des Kontos"),
    ("kronos_kanban_zustand", "JSON-Snapshots des Kontos"),
    ("dm_sitzung", "Dev-Modus-Sitzung"),
    ("dm_befund", "Dev-Modus-Befund"),
    ("dm_ereignis", "Dev-Modus-Ereignis"),
    ("sicherer_anhang", "persönlicher Anhang der Person"),
    # ID-1f: das Umzugsprotokoll der Kennungen (alt -> neu). Es ist kein
    # Nachweis; die Zeile der Person nennt ihren früheren Klarnamen.
    (KENNUNG_ABBILDUNG, "Umzugsprotokoll der Kennungen (früherer Klarname)"),
)

#: Tabellen mit Konto-Bezug, deren Zeilen gelöscht werden — dort wird VORHER
#: nichts genullt (die Zeile verschwindet ohnehin). Muss zu ZEILEN_LOESCHEN
#: passen; `test_dsgvo1_inventar.py` prüft das.
KONTO_ZEILEN = frozenset({
    "has_role", "user_role", "passwortzugang", "auth_oidc_identitaet",
    "auth_zuordnung_ablehnung", "user_notification_preference",
    "dashboard_widget_user_config", "nutzereinzelrechte", "kalender_moderator",
    "gruppe_verantwortlicher", "untergruppe_verantwortlicher",
    "dienstbereich_verantwortlicher", "kronos_kanban_zustand", "dm_sitzung",
    "dm_befund", "dm_ereignis", "sicherer_anhang",
})


# ── Verweise aus den Metadaten ──────────────────────────────────────────────


#: Art → ausführende Funktion. Diese Registry ist die Zusage, dass JEDE Art im
#: Inventar auch gelesen wird (N-4, R-DSGVO-1b): eine neue Art ohne Eintrag
#: bricht `test_dsgvo1_inventar.py::test_jede_inventar_art_ist_implementiert`.
#: Die Funktionen werden am Modulende gebunden (sie stehen erst dort).
INVENTAR_ARTEN: dict[str, object] = {}


def _tabelle(name: str):
    from diakronos_app.models.base import Base

    for mapper in Base.registry.mappers:
        if mapper.local_table.name == name:
            return mapper.local_table
    return None


def _tabellen() -> list:
    """Alle Tabellen der Metadaten, stabil sortiert (Reproduzierbarkeit)."""
    from diakronos_app.models.base import Base

    gesehen, ergebnis = set(), []
    for mapper in Base.registry.mappers:
        tabelle = mapper.local_table
        if tabelle.name in gesehen:
            continue
        gesehen.add(tabelle.name)
        ergebnis.append(tabelle)
    return sorted(ergebnis, key=lambda t: t.name)


def verweise() -> dict[str, list[tuple[str, str]]]:
    """Alle Fremdschlüssel-Spalten auf `mitglied.name` bzw. `user.name`.

    Abgeleitet aus `Base.metadata` — NICHT von Hand gepflegt. Rückgabe:
    ``{"mitglied": [(tabelle, spalte), …], "user": [...]}``. Eine neue FK in
    einem späteren DocType erscheint hier automatisch; der Wächtertest
    `test_dsgvo1_inventar.py::test_jede_fk_auf_mitglied_oder_user_ist_versorgt`
    schlägt fehl, wenn sie keine Entscheidung im Inventar hat.
    """
    ergebnis: dict[str, list[tuple[str, str]]] = {"mitglied": [], "user": []}
    for tabelle in _tabellen():
        for spalte in tabelle.c:
            for fk in spalte.foreign_keys:
                ziel = str(fk.target_fullname or "")
                if ziel in ("mitglied.name", "user.name"):
                    ziel_tabelle = ziel.split(".")[0]
                    ergebnis[ziel_tabelle].append((tabelle.name, spalte.name))
    for werte in ergebnis.values():
        werte.sort()
    return ergebnis


# ── Bestand ─────────────────────────────────────────────────────────────────


def bestand_erheben(s, mitglied: str, konten) -> Bestand:
    """Sammelt Name, Mail, Telefon und Anmeldungen der Person (lesend)."""
    from diakronos_app.models.core import User
    from diakronos_app.models.diakonos import Anmeldung, Mitglied

    b = Bestand(mitglied=mitglied, konten={str(k) for k in (konten or ()) if k})
    b.adressen |= b.konten  # user.name IST die Adresse
    m = s.get(Mitglied, mitglied)
    if m is not None:
        vor = str(getattr(m, "vorname", "") or "").strip()
        nach = str(getattr(m, "nachname", "") or "").strip()
        _merke_name(b, vor, nach)
        _merke(b, getattr(m, "email", None))
        _merke(b, getattr(m, "telefonnummer", None), telefon=True)
        for feld in ("wohnort", "straße", "postleitzahl"):
            _merke(b, getattr(m, feld, None), ort=True)
        geburtstag = getattr(m, "geburtstag", None)
        if geburtstag:
            for form in (str(geburtstag), geburtstag.strftime("%d.%m.%Y"),
                         geburtstag.strftime("%d.%m.%y")):
                _merke(b, form, ort=True)
        for feld in ("foto",):
            wert = str(getattr(m, feld, "") or "").strip()
            if wert:
                b.dateien.add(wert)
    _fruehere_kennungen(s, b)
    if b.konten:
        for u in s.scalars(select(User).where(User.name.in_(b.konten))).all():
            _merke(b, u.email)
            # N-6: `user.full_name` ist der Anzeigename EINER Person. Nur ein
            # Konto der gelöschten Person zählt hier — ein anderes Konto mit
            # demselben Vollnamen hat seinen Namen selbst.
            voll = str(u.full_name or "").strip()
            if voll.casefold() != str(u.email or "").strip().casefold():
                teile = voll.replace(",", " ").split()
                if len(teile) >= 2:
                    b.namen.add(voll)
                    b.namen.add(f"{teile[-1]}, {' '.join(teile[:-1])}")
                elif teile:
                    b.namensteile.add(voll)
            if u.user_image:
                b.dateien.add(str(u.user_image))
    b.anmeldungen = set(s.scalars(
        select(Anmeldung.name).where(Anmeldung.mitglied == mitglied)
    ).all())
    for name in b.anmeldungen:
        a = s.get(Anmeldung, name)
        if a is None:
            continue
        # N-1: vorname/nachname der Anmeldung sind EINZELTEILE. Sie werden
        # nur als Paar zur Nadel — sonst trifft „Dorn“ jeden Namensvetter.
        _merke_name(b, getattr(a, "vorname", None), getattr(a, "nachname", None))
        for feld in ("email", "email_freitext", "name_freitext", "telefon"):
            _merke(b, getattr(a, feld, None))
    for konto in b.konten:
        b.adressen.add(str(konto))
    # Benachrichtigungstexte der Person: sie nennen den Namen im Fließtext
    # („Annamaria Beispielhuber hat …“) — der Wert steht in keiner Spalte, die
    # nach dem Namen durchsucht wird.
    if b.konten:
        for zeile in _meldungen_der_person(s, b):
            for feld in ("subject", "email_content"):
                text_ = str(getattr(zeile, feld, "") or "").strip()
                if text_:
                    b.meldungen.add(text_)
    return b


def _vorhandene_tabellen(s) -> set[str] | None:
    """Welche Tabellen gibt es in DIESER Datenbank? — ``None`` = unbekannt.

    Ein Katalog-Lesevorgang für die ganze Löschung statt einer Frage je Tabelle.
    Wie `_hat_tabelle` über die GEHALTENE Verbindung: `sqlalchemy.inspect(...)
    .has_table()` fragt über eine eigene Verbindung und reißt auf einer Datenbank
    mit EINER Verbindung je Engine (SQLite StaticPool der Tests) den SAVEPOINT
    des Aufrufers mit („no such savepoint“).
    """
    from sqlalchemy import text as _text

    try:
        return {str(n) for n in s.execute(_text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = current_schema()")).scalars().all()}
    except Exception:  # noqa: BLE001 — SQLite kennt information_schema nicht
        try:
            return {str(n) for n in s.execute(_text(
                "SELECT name FROM sqlite_master WHERE type = 'table'")).scalars().all()}
        except Exception:  # noqa: BLE001 — kein Katalog lesbar: fail closed
            return None


def _hat_tabelle(s, name: str) -> bool:
    """Gibt es Tabelle `name`? — ohne eine zweite Verbindung zu oeffnen."""
    vorhanden = _vorhandene_tabellen(s)
    if vorhanden is None:
        return False
    return name in vorhanden


def _hat_kennungstabelle(s) -> bool:
    """Gibt es `id1_mitglied_kennung`? — die Frage des Löschpfads (ID-1f)."""
    return _hat_tabelle(s, KENNUNG_ABBILDUNG)


def _fruehere_kennungen(s, b: Bestand) -> None:
    """Frühere Kennungen der Person aus dem Umzugsprotokoll merken (ID-1f).

    `id1_mitglied_kennung` hält `alt` -> `neu` der Migration ID-1: `alt` ist die
    Form VOR dem Umschlüsseln (im Betrieb der Klarname), `neu` die Kennung
    seither. Nachweiszeilen aus der Zeit davor führen den Namensanteil `alt`
    (`DSGVO-<alt>-0002`), obwohl die Person heute unter `neu` steht.

    Gemerkt wird deshalb BEIDES, sobald eine Zeile die Person nennt — `neu` ist
    die heutige Kennung, `alt` die, unter der ihre Nachweise noch laufen
    können. Gelesen wird über beide Spalten: nach einem zweiten Lauf kann die
    bekannte Kennung auch in `alt` stehen.

    TRANSITIVE HÜLLE (Punkt 3): ein zweiter Umschlüsselungs-Lauf hängt eine
    weitere Stufe an (A -> B, B -> C). Eine Suche in EINER Stufe fände nur B —
    die Zeile mit A bliebe mit dem Klarnamen stehen. Deshalb wird gelesen, bis
    keine neue Kennung mehr dazukommt (endlich: `alt` ist Primärschlüssel, jede
    Zeile wird höchstens einmal gelesen).

    Existiert die Tabelle nicht (Downgrade, ältere DB), gibt es nichts zu
    merken — die Löschung läuft unverändert durch.
    """
    if not _hat_kennungstabelle(s):
        return
    b.kennungen.add(b.mitglied)
    fremde = _tabelle(KENNUNG_ABBILDUNG)
    if fremde is None or fremde.c.get("neu") is None or fremde.c.get("alt") is None:
        return
    while True:
        vorher = len(b.kennungen)
        for zeile in s.execute(
                select(fremde.c.alt, fremde.c.neu).where(
                    or_(fremde.c.alt.in_(b.kennungen),
                        fremde.c.neu.in_(b.kennungen)))).all():
            for wert in zeile:
                if wert:
                    b.kennungen.add(str(wert))
        b.kennungen.discard("")
        if len(b.kennungen) == vorher:
            return


def _meldungen_der_person(s, b: Bestand):
    """Benachrichtigungen, die an dieses Konto adressiert sind (lesend)."""
    from diakronos_app.models.core import NotificationLog

    return s.scalars(select(NotificationLog).where(
        NotificationLog.for_user.in_(b.konten))).all()


def _merke(b: Bestand, wert, *, telefon: bool = False, ort: bool = False) -> None:
    auf = str(wert or "").strip()
    if not auf:
        return
    if ort:
        b.orte.add(auf)
    elif telefon:
        b.telefon.add(auf)
    elif "@" in auf:
        b.adressen.add(auf)
    else:
        b.namensteile.add(auf)


def _merke_name(b: Bestand, vor, nach) -> None:
    """Name aus Vorname/Nachname: als PAAR eine Nadel, einzeln nur Suchwert.

    N-1 (R-DSGVO-1b): „Vorname Nachname“ und „Nachname, Vorname“ sind volle
    Nennungen und werden in fremden Texten ersetzt. Ein einzelner Teil („Dorn“)
    steht dort auch bei ANDEREN Personen („Hendrik Dorn“) — er wird deshalb nur
    gemerkt, nicht gesucht. Das gilt auch, wenn die Person nur einen Namen hat.
    """
    vor = str(vor or "").strip()
    nach = str(nach or "").strip()
    for teil in (vor, nach):
        if len(teil) > 1:
            b.namensteile.add(teil)
    if vor and nach:
        b.namen.add(f"{vor} {nach}")
        b.namen.add(f"{nach}, {vor}")


# ── Anonymisierung ──────────────────────────────────────────────────────────


def neue_kennung() -> str:
    """Neue neutrale Mitglied-Kennung: `geloescht-<zufällige hex>`."""
    return f"{GELOESCHT_PRAEFIX}{uuid4().hex}"


def anonymisiere(s, mitglied: str, konten, *, dateien: list[str] | None = None) -> dict:
    """Führt die vollständige Anonymisierung in der Transaktion des Aufrufers aus.

    Reihenfolge (jeder Schritt ist Voraussetzung des nächsten):

    1. **Bestand** lesen (vor dem ersten Schreibzugriff — danach steht der Name
       nicht mehr in `mitglied`).
    2. **Dateien merken** (Profilbild, `user_image`, Anhänge, Screenshot).
    3. **Verweise umhängen**: die neue Zeile mit der neutralen Kennung anlegen,
       alle FKs auf `mitglied.name` und alle Wert-Spalten (JSON, `*_name`)
       umschreiben, alte Zeile löschen.
    4. **Konto auflösen**: Verweise auf `user` nullen bzw. auf den Platzhalter,
       Konto-Zeilen löschen.
    5. **Eigene Zeilen** leeren bzw. löschen (Anmeldungen, Protokolle, Meldungen).
    6. **Fremdtexte**: nur volle Namen, Adressen und Telefonnummern als ganzes
       Wort ersetzen.
    7. **Flush** — hier treten alle FK-/Constraint-Fehler auf, VOR dem Mailversand.

    Rückgabe: ``{"zaehler", "bestand", "suchwerte", "kennung", "dateien"}``.
    """
    from diakronos_app.models.diakonos import Anmeldung, Mitglied

    b = bestand_erheben(s, mitglied, konten)
    zaehler: dict[str, int] = {}
    kennung = neue_kennung()

    # 0) Ein Rest vom Platzhalter-Konto (Verweis-Ziel, keine Person) wird
    #    aufgelöst, damit keine Zeile darauf zeigt.
    zaehler.update(_platzhalter_aufloesen(s))

    # 1) Selbstbezüge der Mitglieder auf die Person lösen: sonst blockiert die
    #    FK die Löschung der alten Zeile.
    tabelle = _tabelle("mitglied")
    for spalte_name in ("ehepartner", "elternteil"):
        spalte = tabelle.c.get(spalte_name) if tabelle is not None else None
        if spalte is None:
            continue
        _zaehle(s, zaehler, f"mitglied.{spalte_name}", update(tabelle)
                .where(spalte == mitglied).values({spalte.key: None}))

    # 2) NEUE Zeile mit neutraler Kennung: nur technische Felder, kein Name.
    neu_angelegt = _neue_zeile(s, mitglied, kennung)
    if neu_angelegt:
        zaehler["mitglied.neu"] = neu_angelegt

    # 3) Verweise umhängen: FKs aus den Metadaten + Wert-Spalten (JSON/Namen).
    zaehler.update(_verweise_umhaengen(s, mitglied, kennung, bestand_=b))

    # 3c) Datei-Pfade der Person einsammeln, BEVOR Zeilen fallen (N-3: die
    #     `sicherer_anhang`-Zeile wird in Schritt 7 gelöscht, in Schritt 11 wäre
    #     ihr `datei`-Pfad nicht mehr lesbar).
    _dateipfade_sammeln(s, b, kennung)

    # 4) Alte Zeile löschen — ab hier trägt nur noch die neutrale Kennung.
    _zaehle(s, zaehler, "mitglied.alt", delete(Mitglied).where(Mitglied.name == mitglied))

    # 5) Eigene Protokollzeilen ZUERST: sie filtern ueber `actor`/`target_user`
    #    (Konten) und `target_name` (Kennung). Stuenden diese Verweise vorher
    #    auf NULL, liefe der Filter ins Leere — genau der Reihenfolgefehler aus
    #    H3 (R-DSGVO-1: `actor` wurde VOR Schritt 3b genullt).
    zaehler.update(_eigene_protokolle(s, b, kennung))

    # 6) Konto-Verweise aufloesen, dann die Konto-Zeilen loeschen.
    zaehler.update(_konto_verweise_aufloesen(s, b))

    # 6b) Spalten OHNE Fremdschlüssel: Bucher (Kennung + Name), Autoren und die
    #     Konto-Mails im JSON des Planrahmens (N-2, R-DSGVO-1b).
    zaehler.update(_platzhalter_spalten(s, b))
    zaehler.update(_autoren_neutralisieren(s, b))
    # 6c) Komma-Listen (BACKUP-1 `sicherungslauf.benachrichtigt`): Eintrag der
    #     Person EXAKT entfernen, nicht als Fremdtext ersetzen.
    zaehler.update(_konto_listen_bereinigen(s, b))

    if b.konten:
        from diakronos_app.models.core import User

        _zaehle(s, zaehler, "user", delete(User).where(User.name.in_(b.konten)))

    # 6) Anmeldungen: Stammdaten leeren, Kinder und Antworten löschen.
    if b.anmeldungen:
        _zaehle(s, zaehler, "anmeldung", update(Anmeldung)
                .where(Anmeldung.name.in_(b.anmeldungen))
                .values(vorname=None, nachname=None, email=None, telefon=None,
                        geburtstag=None, ip_adresse=None, kommentar=None,
                        name_freitext=None, email_freitext=None))

    # 6d) Die Adresse der Person gilt für Löschen und Nullen wie ein Konto
    #     (R-DSGVO-1c, offene Frage): `mitglied.email` steht im Betrieb auch
    #     ohne `user`-Zeile in Spalten ohne Fremdschlüssel — `wirksame_konten`
    #     bleibt unverändert, der Löschpfad erweitert sich hier.
    b.konten = _konto_werte(s, b)

    # 7) Zeilen löschen, die ganz verschwinden (Zugang, Beziehungen, Snapshots).
    zaehler.update(_zeilen_loeschen(s, b, kennung))

    # 8) Protokolle: `audit_log.target_name` trägt bei Konto-Eingriffen die
    #    Konto-Mail — auf den neutralen Namen setzen (N-2). EXAKTER Vergleich.
    zaehler.update(_audit_zielnamen(s, b))

    # 9) Benachrichtigungen: eigene neutral setzen; fremde nennen die Person
    #    nur im Text (Schritt 10).
    zaehler.update(_benachrichtigungen_neutralisieren(s, b, kennung))

    # 9b) Geräteangaben der Einwilligungen (M3, Fachentscheidung: „vollständig
    #     heißt vollständig“). Die Zeile bleibt als Nachweis (Art. 7), IP und
    #     Browserkennung sind personenbezogen und gehen.
    zaehler.update(_einwilligungen_entpersonalisieren(s, kennung, b.mitglied))

    # 10) Fremdtexte: NUR volle Namen, Adressen und Telefonnummern als GANZES
    #     WORT. Wohnort/PLZ/Straße/Vorname bleiben stehen (Fachentscheidung).
    zaehler.update(_fremdtexte_ersetzen(s, b))
    # 10b) Nachweiszeilen: der SCHLÜSSEL darf weder den Namen noch die Kennung
    #      der Person führen (ID-1f, Vollscan = 0 Treffer): Kennungsregel
    #      umschreiben, danach Klarnamen-Suche. NACH `_konto_werte` — das
    #      ERSETZT `b.konten`, und die früheren Kennungen (`b.kennungen`) sind
    #      davon unabhängig.
    zaehler.update(_eigene_schluessel_ersetzen(s, b, kennung))

    # 11) Dateien der Person: Datei-Spalten und Anhänge (physisch nach Commit).
    zaehler.update(_eigene_dateien(s, b, kennung))

    # 12) FLUSH: alle FK-/Constraint-Fehler treten HIER auf — vor dem Mailversand.
    #     Der Aufrufer sendet erst danach und rollt bei einem Fehler zurück.
    _pruefe_konsistenz(s)

    if dateien is not None:
        dateien.extend(sorted(b.dateien))
    return {"zaehler": zaehler, "bestand": b, "suchwerte": b.suchwerte,
            "kennung": kennung, "dateien": sorted(b.dateien)}


def _neue_zeile(s, alt: str, kennung: str) -> int:
    """Kopie der Mitglied-Zeile unter NEUER Kennung — nur technische Felder.

    Positivliste (N-2/B aus R-DSGVO-1b): übernommen werden ausschließlich
    `_MITGLIED_TECHNISCH` (Anlage-/Änderungszeit, `docstatus`, `idx`). Jede
    andere Spalte — auch eine, die erst später entsteht — startet leer und
    wird dann von `_mitglied_werte()` gesetzt bzw. bleibt NULL.
    """
    from diakronos_app.models.diakonos import Mitglied

    quelle = s.get(Mitglied, alt)
    if quelle is None:
        return 0
    werte: dict = {}
    for spalte in Mitglied.__table__.c:
        if spalte.name == "name":
            continue
        werte[spalte.name] = (getattr(quelle, spalte.name, None)
                              if spalte.name in _MITGLIED_TECHNISCH else None)
    werte.update(_mitglied_werte())
    s.add(Mitglied(name=kennung, **werte))
    s.flush()
    return 1


def _mitglied_werte() -> dict:
    """Zielzustand der Mitglied-Zeile (D5): keine Personendaten mehr."""
    return {
        "vorname": VORNAME, "nachname": NACHNAME,
        "email": None, "telefonnummer": None, "postleitzahl": None,
        "wohnort": None, "straße": None, "nummer": None, "geburtstag": None,
        "foto": None, "notiz": None, "geschlecht": None, "familienstand": None,
        "ehepartner": None, "elternteil": None, "mitglied_seit": None,
        "ancestor_path": None, "user": None,
        "auf_bemerkung_gesetzt": False, "auf_bemerkung_gesetzt_seit": None,
        "datenschutz_einwilligung": False, "foto_einwilligung": False,
        "werbeeinwilligung": False,
        "datenschutz_datum": None, "foto_datum": None, "werbung_datum": None,
        "adressbuch_sichtbarkeit": "{}",
        # Endstatus: `_pruefe_mitglied_schreibzugriff` verweigert danach JEDE
        # Änderung (H2) — die Löschung ist nicht rückgängig zu machen.
        "ausgeschlossen": True,
        "ausgeschlossen_seit": datetime.utcnow().date(),
        "status": "geloescht",
    }


def _verweise_umhaengen(s, alt: str, kennung: str, *, bestand_) -> dict:
    """Alle Verweise auf die alte Kennung auf die neue umschreiben.

    Quelle der Wahrheit sind die Metadaten (`verweise()`); das Inventar
    (`SPALTEN`, `WERT_SPALTEN`) ergänzt Spalten OHNE Fremdschlüssel.
    """
    zaehler: dict[str, int] = {}
    fks = verweise()
    for ziel_tabelle, paare in fks.items():
        for tabelle_name, spaltenname in paare:
            tabelle = _tabelle(tabelle_name)
            spalte = tabelle.c.get(spaltenname) if tabelle is not None else None
            if spalte is None:
                continue
            art = SPALTEN.get(tabelle_name, {}).get(spaltenname, ("", ""))[0]
            if art == "mitglied_null":
                # Selbstbezug: schon in Schritt 1 geleert, nichts zu tun.
                continue
            if ziel_tabelle == "user":
                continue  # Konto-Verweise: Schritt 5
            _zaehle(s, zaehler, f"{tabelle_name}.{spaltenname}", update(tabelle)
                    .where(spalte == alt).values({spalte.key: kennung}))
    # Wert-Spalten ohne FK: ganze Spalte oder JSON-Wert.
    for tabelle_name, spalten in WERT_SPALTEN.items():
        tabelle = _tabelle(tabelle_name)
        if tabelle is None:
            continue
        for spaltenname, art in spalten.items():
            spalte = tabelle.c.get(spaltenname)
            if spalte is None:
                continue
            schluessel = f"{tabelle_name}.{spaltenname}"
            if art == "wert":
                _zaehle(s, zaehler, schluessel, update(tabelle)
                        .where(spalte == alt).values({spalte.key: kennung}))
            else:
                zaehler[schluessel] = zaehler.get(schluessel, 0) + _json_umhaengen(
                    s, tabelle, spalte, alt, kennung
                )
    return zaehler


def _json_umhaengen(s, tabelle, spalte, alt: str, kennung: str | None) -> int:
    """JSON-Spalte: jeder Wert, der GENAU `alt` ist, wird durch `kennung` ersetzt.

    Nur der ganze Wert — ein Teilstring-Treffer würde fremde Texte zerstören
    (genau der Fehler aus K2). Der Vergleich läuft portabel in Python (SQLite
    und PostgreSQL): die Zeilen sind wenige, und ein JSON-Pfad-Ausdruck wäre
    je Dialekt eine eigene Baustelle. `kennung=None` leert den Wert (N-2:
    Konto-Mails in `pr_verlauf`/`pr_plan`).
    """
    pk = list(tabelle.primary_key.columns)
    if not pk:
        return 0
    treffer = 0
    anweisung = select(*pk, spalte)
    for zeile in s.execute(anweisung).all():
        *schluessel, wert = zeile
        if wert is None:
            continue
        neu = _json_ersetzen(wert, alt, kennung)
        if neu == wert:
            continue
        bedingung = and_(*[c == w for c, w in zip(pk, schluessel)])
        s.execute(update(tabelle).where(bedingung).values({spalte.key: neu}))
        treffer += 1
    return treffer


def _json_ersetzen(wert, alt: str, kennung: str | None):
    """Ersetzt in einem JSON-Baum jeden Wert, der GENAU `alt` ist."""
    if isinstance(wert, str):
        return kennung if wert == alt else wert
    if isinstance(wert, list):
        return [_json_ersetzen(x, alt, kennung) for x in wert]
    if isinstance(wert, dict):
        return {k: _json_ersetzen(v, alt, kennung) for k, v in wert.items()}
    return wert


def _konto_verweise_aufloesen(s, b: Bestand) -> dict:
    """Verweise auf das KONTO auflösen, bevor die `user`-Zeile fällt.

    * FKs auf `user.name`, deren Zeile bleibt: NULLen (bzw. Platzhalter, wo
      das Inventar es so sagt).
    * Inventar-Einträge der Art `user_null` OHNE Fremdschlüssel (`N-2`:
      `pr_verlauf.benutzer`, `pr_plantyp_version.erstellt_von` …): dieselbe
      Behandlung, sonst wären sie toter Buchstabe.
    * Frappe-Protokollspalten (`owner`/`modified_by`/`created_by`/`from_user`)
      tragen den Kontonamen auf JEDER Tabelle: hier zentral nullen — ein
      Inventar-Eintrag je Tabelle müsste 200 Zeilen wiederholen.
    """
    zaehler: dict[str, int] = {}
    if not b.konten:
        return zaehler
    fk_spalten = set(verweise()["user"])
    for tabelle_name, spalten in SPALTEN.items():
        if tabelle_name in KONTO_ZEILEN:
            continue  # Zeile wird ohnehin gelöscht
        tabelle = _tabelle(tabelle_name)
        if tabelle is None:
            continue
        for spaltenname, (art, _grund) in spalten.items():
            if art not in ("user_null", "user_platzhalter"):
                continue
            if (tabelle_name, spaltenname) in fk_spalten:
                continue  # unten über die Metadaten erledigt
            spalte = tabelle.c.get(spaltenname)
            if spalte is None:
                continue
            wert = GELOESCHTES_KONTO if art == "user_platzhalter" else None
            _zaehle(s, zaehler, f"{tabelle_name}.{spaltenname}", update(tabelle)
                    .where(spalte.in_(b.konten)).values({spalte.key: wert}))
    for tabelle_name, spaltenname in verweise()["user"]:
        if tabelle_name in KONTO_ZEILEN:
            continue  # Zeile wird ohnehin gelöscht
        tabelle = _tabelle(tabelle_name)
        spalte = tabelle.c.get(spaltenname) if tabelle is not None else None
        if spalte is None:
            continue
        art = SPALTEN.get(tabelle_name, {}).get(spaltenname, ("user_null", ""))[0]
        wert = GELOESCHTES_KONTO if art == "user_platzhalter" else None
        _zaehle(s, zaehler, f"{tabelle_name}.{spaltenname}", update(tabelle)
                .where(spalte.in_(b.konten)).values({spalte.key: wert}))
    # Konto-Mails in JSON-Spalten des Planrahmens (`vorher`/`nachher`,
    # `veroeffentlichter_stand`): EXAKTER Wert-Vergleich, kein Teilstring.
    for tabelle_name, spalten in WERT_SPALTEN.items():
        if tabelle_name in KONTO_ZEILEN:
            continue
        tabelle = _tabelle(tabelle_name)
        if tabelle is None:
            continue
        for spaltenname, art in spalten.items():
            if art != "json":
                continue
            spalte = tabelle.c.get(spaltenname)
            if spalte is None:
                continue
            for konto in sorted(b.konten):
                schluessel = f"{tabelle_name}.{spaltenname}"
                zaehler[schluessel] = zaehler.get(schluessel, 0) + _json_umhaengen(
                    s, tabelle, spalte, konto, None
                )
    # Protokollspalten ohne FK.
    for tabelle in _tabellen():
        for name in ("owner", "modified_by", "created_by", "from_user"):
            spalte = tabelle.c.get(name)
            if spalte is None or not isinstance(spalte.type, (String, Text)):
                continue
            _zaehle(s, zaehler, f"{tabelle.name}.{name}", update(tabelle)
                    .where(spalte.in_(b.konten)).values({spalte.key: None}))
    return zaehler


def _platzhalter_spalten(s, b: Bestand) -> dict:
    """`mitglied_platzhalter`: Kennung bzw. Name des Buchers neutral setzen (N-2).

    `ressourcen_buchung.gebucht_von` trägt die Konto-Mail, `…_name` den
    Klarnamen — beides ohne Fremdschlüssel. Verglichen wird der EXAKTE Wert
    (Kennung, Konto, Name, Anmeldung), nie ein Teilstring. Die Buchung selbst
    bleibt als Fachvorgang stehen (`_MITGLIED_PLATZHALTER`).
    """
    zaehler: dict[str, int] = {}
    # Nur VOLLE Nennungen (R-DSGVO-1c Punkt 5): Kennung, Konto, Adresse und
    # volle Namen — NIE ein einzelner Namensteil. Ein fremder Beitrag oder
    # eine fremde Buchung mit Autor genau „Elvira“ gehört nicht der Person.
    werte = set(b.konten) | b.namen | b.adressen
    werte.add(b.mitglied)
    spalten: list[tuple[str, str]] = []
    for tabelle_name, felder in SPALTEN.items():
        if tabelle_name in {name for name, _ in ZEILEN_LOESCHEN}:
            continue
        for spaltenname, (art, _grund) in felder.items():
            if art == "mitglied_platzhalter":
                spalten.append((tabelle_name, spaltenname))
    for tabelle_name, spaltenname in spalten:
        tabelle = _tabelle(tabelle_name)
        spalte = tabelle.c.get(spaltenname) if tabelle is not None else None
        if spalte is None:
            continue
        if spaltenname.endswith("_name"):
            _zaehle(s, zaehler, f"{tabelle_name}.{spaltenname}", update(tabelle)
                    .where(spalte.in_(werte)).values({spalte.key: ANZEIGENAME}))
        else:
            _zaehle(s, zaehler, f"{tabelle_name}.{spaltenname}", update(tabelle)
                    .where(spalte.in_(werte)).values({spalte.key: None}))
    return zaehler


def _autoren_neutralisieren(s, b: Bestand) -> dict:
    """Autor/Autor-Mail in Beiträgen, Kommentaren und Wiki (N-2).

    Erkannt wird die Person am EXAKTEN Wert ihrer Adresse oder ihres Namens in
    `autor_email` bzw. `autor` — der Beitragsinhalt bleibt stehen (er ist das
    Fachdatum, kein Personenbezug).
    """
    zaehler: dict[str, int] = {}
    # Nur VOLLE Nennungen (R-DSGVO-1c Punkt 5): ein Beitrag mit Autor genau
    # „Elvira“ gehört einer anderen Person mit diesem Vornamen.
    namen = b.konten | b.adressen | b.namen | {b.mitglied}
    for tabelle_name in AUTOR_SPALTEN:
        tabelle = _tabelle(tabelle_name)
        if tabelle is None:
            continue
        spalte_name, spalte_mail = AUTOR_SPALTEN[tabelle_name]
        spalte_autor = tabelle.c.get(spalte_name)
        spalte_adresse = tabelle.c.get(spalte_mail)
        if spalte_adresse is None:
            continue
        bedingungen = [spalte_adresse.in_(namen)]
        if spalte_autor is not None:
            bedingungen.append(spalte_autor.in_(namen))
        eigene = or_(*bedingungen)
        if spalte_autor is not None:
            _zaehle(s, zaehler, f"{tabelle_name}.{spalte_name}", update(tabelle)
                    .where(and_(eigene, spalte_autor.in_(namen)))
                    .values({spalte_autor.key: ANZEIGENAME}))
        _zaehle(s, zaehler, f"{tabelle_name}.{spalte_mail}", update(tabelle)
                .where(and_(eigene, spalte_adresse.is_not(None)))
                .values({spalte_adresse.key: None}))
    return zaehler


def _audit_zielnamen(s, b: Bestand) -> dict:
    """`audit_log.target_name` neutralisieren, wenn dort die Konto-Mail steht.

    N-2 (R-DSGVO-1b): Bei einem Eingriff am KONTO (`target_doctype='User'`)
    steht die Adresse in `target_name`; die Wert-Spalten-Suche kennt nur die
    Mitglieds-Kennung. Die Protokollzeile bleibt — ihr Ziel wird neutral.
    """
    zaehler: dict[str, int] = {}
    if not b.konten:
        return zaehler
    tabelle = _tabelle("audit_log")
    if tabelle is None or tabelle.c.get("target_name") is None:
        return zaehler
    _zaehle(s, zaehler, "audit_log.target_name", update(tabelle)
            .where(tabelle.c["target_name"].in_(b.konten))
            .values({tabelle.c["target_name"].key: ANZEIGENAME}))
    return zaehler


def _dateipfade_sammeln(s, b: Bestand, kennung: str) -> None:
    """Datei-Verweise einsammeln, solange die Zeilen noch da sind (N-3).

    `sicherer_anhang` verschwindet in `_zeilen_loeschen`; `bug_report` bleibt,
    seine Spalte wird geleert. Beide Pfade müssen VOR Schritt 7 gelesen sein,
    sonst ist die Datei danach verwaist im Speicher (kein Verweis mehr in der DB
    — aber auch kein Löschauftrag).
    """
    for tabelle_name, spaltenname in (("sicherer_anhang", "datei"),
                                      ("bug_report", "screenshot")):
        tabelle = _tabelle(tabelle_name)
        if tabelle is None or tabelle.c.get(spaltenname) is None:
            continue
        spalte = tabelle.c[spaltenname]
        bedingungen = []
        if tabelle.c.get("mitglied") is not None:
            bedingungen.append(tabelle.c["mitglied"].in_([b.mitglied, kennung]))
        if b.konten and tabelle.c.get("benutzer") is not None:
            bedingungen.append(tabelle.c["benutzer"].in_(b.konten))
        if not bedingungen:
            continue
        for wert in s.scalars(select(spalte).where(or_(*bedingungen))).all():
            if wert:
                b.dateien.add(str(wert))


def _zeilen_loeschen(s, b: Bestand, kennung: str) -> dict:
    """Zeilen, die ganz verschwinden: Zugang, Beziehungen, Snapshots."""
    zaehler: dict[str, int] = {}
    for tabelle_name, _grund in ZEILEN_LOESCHEN:
        tabelle = _tabelle(tabelle_name)
        if tabelle is None:
            continue
        if tabelle_name == KENNUNG_ABBILDUNG:
            # ID-1f: Umzugsprotokoll OHNE Bezugsspalte auf `mitglied`. Die
            # Zeile(n) der Person werden über JEDE ihrer Kennungen erkannt —
            # die aktuelle/neue in `neu`, die frühere (Klarname) in `alt`.
            # Deshalb braucht es BEIDE Zweige: steht die Person nur in `neu`
            # (Abbildung nach einem zweiten Lauf), findet sie nur dieser.
            # Fehlt die Tabelle (Downgrade, ältere DB), gibt es hier nichts zu
            # löschen: `_fruehere_kennungen` hat dann auch nichts gemerkt.
            #
            # Die aktuelle Kennung steht NICHT zwingend in `b.kennungen` (die
            # Sammlung füllt `_fruehere_kennungen`): sie wird deshalb wie die
            # anderen Fälle über `b.mitglied` UND `kennung` gesucht. Und ein
            # leeres `IN ()` ist kein „nichts gefunden“, sondern ein Prädikat
            # ohne Typ — in einer OR-Liste trifft es gar nichts. Zweige mit
            # leerer Werteliste fallen deshalb weg.
            spalte = tabelle.c.get("alt")
            neu = tabelle.c.get("neu")
            if spalte is None or neu is None or not _hat_kennungstabelle(s):
                continue
            gesucht = sorted((set(b.kennungen) | {b.mitglied, kennung}) - {""})
            zweige = [c.in_(gesucht) for c in (spalte, neu) if gesucht]
            if zweige:
                _zaehle(s, zaehler, tabelle_name, delete(tabelle).where(or_(*zweige)))
            continue
        bedingungen = []
        for c in tabelle.c:
            if c.name in ("user", "nutzer", "benutzer") and b.konten:
                bedingungen.append(c.in_(b.konten))
            elif c.name == "mitglied":
                # N-3: `pr_abwesenheit` und `sicherer_anhang` haben WEDER
                # `parent` NOCH eine Konto-Spalte — ohne diesen Zweig entstand
                # keine Bedingung und die Zeile blieb (Gesundheitsfreitext).
                bedingungen.append(c.in_([b.mitglied, kennung]))
            elif c.name == "parent":
                if b.konten:
                    bedingungen.append(c.in_(b.konten))
                bedingungen.append(c.in_([b.mitglied, kennung]))
                # Kindzeilen der Anmeldungen: `parent` ist der Name der
                # Anmeldung, nicht der Person (`anmeldung_antwort`,
                # `anmeldung_kind`). Ohne diesen Zweig blieben Namen von
                # Angehörigen stehen.
                if b.anmeldungen:
                    bedingungen.append(c.in_(b.anmeldungen))
            elif c.name == "for_user" and b.konten:
                bedingungen.append(c.in_(b.konten))
        if tabelle_name == "mitglied_beziehung":
            # Beide Richtungen: die Zeilen der Person UND die Zeilen ANDERER,
            # die auf sie zeigen (N7 wie main).
            spalte = tabelle.c.get("beziehung_zu")
            if spalte is not None:
                bedingungen.append(spalte.in_([b.mitglied, kennung]))
        if tabelle_name == "auth_zuordnung_ablehnung" and tabelle.c.get("email") is not None:
            bedingungen.append(tabelle.c["email"].in_(b.adressen | b.namen))
        if not bedingungen:
            continue
        # R-DSGVO-1c: `parent` allein trifft auch Frappe-Konfiguration (Page,
        # Report, Workspace, Desktop Icon) und Kalender-Rollen. Eine
        # Zugangszeile der Person ist NUR die mit `parenttype='User'`; die
        # Bedingung wird deshalb UND-verknüpft, nicht in die ODER-Liste
        # gehängt (sonst würde sie als eigene Alternative alles löschen).
        if tabelle_name in ("has_role", "user_role") and tabelle.c.get("parenttype") is not None:
            bedingung = and_(or_(*bedingungen), tabelle.c["parenttype"] == "User")
        else:
            bedingung = or_(*bedingungen)
        _zaehle(s, zaehler, tabelle_name, delete(tabelle).where(bedingung))
    return zaehler


def _eigene_protokolle(s, b: Bestand, kennung: str) -> dict:
    """Protokollzeilen der Person: Geräteangaben und Werte ihrer Felder.

    Reihenfolge ist hier die halbe Miete (H3): erst NACH der Umhängung filtern
    `target_name`/`target_user` auf die neue Kennung. Vorher genullt hätte
    Schritt „nach actor filtern“ nie gegriffen.
    """
    zaehler = _antrags_protokolle(s, b, kennung)
    zaehler.update(_audit_protokolle(s, b, kennung))
    return zaehler


def _antrags_protokolle(s, b: Bestand, kennung: str) -> dict:
    """Freitexte am LÖSCHANTRAG leeren (N2, R-DSGVO-2a).

    `loeschantrag` ist eine eigene Zeile der Person (Primärschlüssel ist die
    Kennung), also läuft die Art `protokoll` des Inventars hier — sonst wäre
    der Eintrag `ablehnung_grund` ein toter Buchstabe. Geleert wird NUR, was
    das Inventar als `protokoll` führt: der Wortlaut einer Ablehnung
    („Frau X ist erkrankt“). Der Nachweis der Entscheidung — Status,
    Zeitpunkt, Konto — bleibt stehen.
    """
    felder = [spaltenname for spaltenname, (art, _grund) in
              SPALTEN.get("loeschantrag", {}).items() if art == "protokoll"]
    zaehler: dict[str, int] = {}
    tabelle = _tabelle("loeschantrag") if felder else None
    if tabelle is None or tabelle.c.get("mitglied") is None:
        return zaehler
    eigene = tabelle.c["mitglied"].in_([kennung, b.mitglied])
    for spaltenname in felder:
        spalte = tabelle.c.get(spaltenname)
        if spalte is None:
            continue
        _zaehle(s, zaehler, f"loeschantrag.{spaltenname}", update(tabelle)
                .where(and_(eigene, spalte.is_not(None)))
                .values({spalte.key: None}))
    return zaehler


def _audit_protokolle(s, b: Bestand, kennung: str) -> dict:
    """Protokollzeilen der Person im Audit-Log: Geräteangaben und Werte."""
    zaehler: dict[str, int] = {}
    tabelle = _tabelle("audit_log")
    if tabelle is None:
        return zaehler
    ziele = [kennung, b.mitglied]
    bedingungen = [tabelle.c["target_name"].in_(ziele)]
    if b.konten:
        bedingungen.append(tabelle.c["actor"].in_(b.konten))
        bedingungen.append(tabelle.c["target_user"].in_(b.konten))
    eigene = or_(*bedingungen)
    for spaltenname in ("ip_address", "user_agent"):
        spalte = tabelle.c.get(spaltenname)
        if spalte is None:
            continue
        _zaehle(s, zaehler, f"audit_log.{spaltenname}", update(tabelle)
                .where(and_(eigene, spalte.is_not(None)))
                .values({spalte.key: None}))
    for spaltenname in ("old_value", "new_value"):
        spalte = tabelle.c.get(spaltenname)
        if spalte is None:
            continue
        _zaehle(s, zaehler, f"audit_log.{spaltenname}", update(tabelle)
                .where(and_(tabelle.c["target_name"].in_(ziele),
                            spalte.is_not(None)))
                .values({spalte.key: FREITEXT_ERSETZUNG}))
    # Fehlerberichte der Person: Browserkennung und Bildschirmfoto.
    bericht = _tabelle("bug_report")
    if bericht is not None:
        bedingungen = []
        if bericht.c.get("mitglied") is not None:
            bedingungen.append(bericht.c["mitglied"].in_(ziele))
        if b.konten and bericht.c.get("benutzer") is not None:
            bedingungen.append(bericht.c["benutzer"].in_(b.konten))
        if bedingungen:
            eigene = or_(*bedingungen)
            spalte = bericht.c.get("user_agent")
            if spalte is not None:
                _zaehle(s, zaehler, "bug_report.user_agent", update(bericht)
                        .where(and_(eigene, spalte.is_not(None)))
                        .values({spalte.key: None}))
    return zaehler


def _einwilligungen_entpersonalisieren(s, kennung: str, alt: str) -> dict:
    """IP und Browserkennung der Einwilligungen der Person löschen (M3).

    Die Zeile selbst bleibt: sie ist der Nachweis der Einwilligung (Art. 7
    Abs. 1). Was geht, sind die Geräteangaben — nach der Umhängung zeigen die
    Zeilen auf die neutrale Kennung.
    """
    zaehler: dict[str, int] = {}
    tabelle = _tabelle("dsgvo_einwilligung")
    if tabelle is None or tabelle.c.get("mitglied") is None:
        return zaehler
    eigene = tabelle.c["mitglied"].in_([kennung, alt])
    for spaltenname in ("ip_adresse", "user_agent"):
        spalte = tabelle.c.get(spaltenname)
        if spalte is None:
            continue
        _zaehle(s, zaehler, f"dsgvo_einwilligung.{spaltenname}", update(tabelle)
                .where(and_(eigene, spalte.is_not(None)))
                .values({spalte.key: None}))
    return zaehler


def _konto_werte(s, b: Bestand) -> set[str]:
    """Die Kennungen, unter denen die Person als KONTO steht — für Löschen/Nullen.

    R-DSGVO-1c, offene Frage: die Kontenliste kommt unverändert aus
    `benutzer_status.wirksame_konten` (die Rechte-Entscheidung bleibt dort).
    Für das Löschen und Nullen gilt zusätzlich die eigene Adresse aus
    `mitglied.email`: der Betrieb kennt Personen ohne `user`-Zeile, deren
    Adresse nur noch in Spalten OHNE Fremdschlüssel steht (`has_role.parent`,
    `dienstbereich_verantwortlicher.user`). Sie ist normalisiert
    (`email_belegung.normalisiere`) und gehört nach der Fachentscheidung
    2026-10-19 zu höchstens EINEM Mitglied.

    Bewusst NICHT dabei: Adressen aus Anmeldungen oder Freitexten — die
    können einem Angehörigen gehören.
    """
    from diakronos_app.email_belegung import normalisiere
    from diakronos_app.models.diakonos import Mitglied

    werte = {str(k) for k in b.konten if str(k).strip()}
    m = s.get(Mitglied, b.mitglied)
    eigene = str(getattr(m, "email", "") or "").strip() if m is not None else ""
    if not eigene:
        # Die Zeile ist zu diesem Zeitpunkt womöglich schon umgehängt; der
        # Bestand hat die Adresse beim Erheben gemerkt.
        eigene = next((a for a in b.adressen if a), "")
    if eigene:
        werte.add(normalisiere(eigene))
    return werte


def _nichts_zu_tun(s, b: Bestand) -> dict:
    """Strukturspalte: beschreibt den LAUF, nicht eine Person.

    Der Eintrag im Inventar ist die Entscheidung selbst — es gibt nichts zu
    löschen. Die Funktion existiert, damit die Art `struktur` einen
    ausführenden Pfad in `INVENTAR_ARTEN` hat (N-4).
    """
    return {}


def _konto_listen_bereinigen(s, b: Bestand) -> dict:
    """Die Adresse der Person aus einer KOMMA-LISTE entfernen.

    `sicherungslauf.benachrichtigt` ist kein Einzelwert, sondern
    ``", ".join(zugestellt)`` (sicherung/lauf.py) — die Adressen der beim
    Fehlschlag benachrichtigten Konten. Ein Fremdtext-Ersatz würde den
    Eintrag durch „[gelöscht]“ ersetzen und die Liste zerschneiden; die
    Adresse wird deshalb als GANZER Eintrag entfernt. Die übrigen Einträge
    bleiben byte-gleich, ihre Reihenfolge ebenso.
    """
    zaehler: dict[str, int] = {}
    werte = {str(w).strip().casefold() for w in (b.adressen | b.konten) if str(w).strip()}
    if not werte:
        return zaehler
    for tabelle_name, felder in WERT_SPALTEN.items():
        for spaltenname, art in felder.items():
            if art != "liste":
                continue
            tabelle = _tabelle(tabelle_name)
            if tabelle is None:
                continue
            spalte = tabelle.c.get(spaltenname)
            pk = list(tabelle.primary_key.columns)
            if spalte is None or not pk:
                continue
            for zeile in s.execute(select(*pk, spalte).where(spalte.is_not(None))).all():
                *schluessel, wert = zeile
                if not wert:
                    continue
                eintraege = str(wert).split(", ")
                reste = [e for e in eintraege if e.strip().casefold() not in werte]
                if len(reste) == len(eintraege):
                    continue
                bedingung = and_(*[c == w for c, w in zip(pk, schluessel)])
                s.execute(update(tabelle).where(bedingung)
                          .values({spalte.key: ", ".join(reste) or None}))
                schluessel_name = f"{tabelle_name}.{spaltenname}"
                zaehler[schluessel_name] = zaehler.get(schluessel_name, 0) + 1
    return zaehler


def _benachrichtigungen_neutralisieren(s, b: Bestand, kennung: str) -> dict:
    """Benachrichtigungen AN die Person neutral setzen.

    Die Zeile bleibt (Nachweis, dass es die Meldung gab), ihr Text nennt
    niemanden mehr. Fremde Benachrichtigungen, die die Person nur im Text
    nennen, behandelt Schritt „Fremdtexte“ (ganzes Wort).
    """
    from diakronos_app.models.core import NotificationLog

    zaehler: dict[str, int] = {}
    bedingungen = []
    if b.konten:
        bedingungen.append(NotificationLog.for_user.in_(b.konten))
    if b.meldungen:
        bedingungen.append(NotificationLog.email_content.in_(b.meldungen))
        bedingungen.append(NotificationLog.subject.in_(b.meldungen))
    if NotificationLog.__table__.c.get("document_name") is not None:
        bedingungen.append(and_(
            NotificationLog.document_type == "Mitglied",
            NotificationLog.document_name == kennung,
        ))
    if not bedingungen:
        return zaehler
    for feld in ("subject", "email_content"):
        spalte = NotificationLog.__table__.c[feld]
        _zaehle(s, zaehler, f"notification_log.{feld}", update(NotificationLog)
                .where(and_(or_(*bedingungen),
                            spalte.is_not(None),
                            spalte != MELDUNG_PLATZHALTER))
                .values({spalte.key: MELDUNG_PLATZHALTER}))
    return zaehler


#: Betreff und Inhalt einer Benachrichtigung, die an die gelöschte Person ging.
#: Beides wird ERSETZT, nicht gelöscht: die Zeile belegt, dass es die Meldung
#: gab — nur ohne Namen.
MELDUNG_PLATZHALTER = "[Benachrichtigung zu einer gelöschten Person]"


def _muster(nadel: str):
    """Wortgrenzen-Muster für eine Nadel (Groß/klein egal, ganze Wörter).

    `\\b` in Python-Regex greift an Wortgrenzen; Umlaute und `ß` zählen in
    `str`-Mustern als Wortzeichen. Telefonnummern und Adressen enthalten
    Satzzeichen, deshalb wird das Muster am Rand auf „kein Wortzeichen“
    geprüft statt auf `\\b` zu vertrauen.
    """
    return re.compile(r"(?<!\w)" + re.escape(nadel) + r"(?!\w)", re.IGNORECASE)


def _fremdtexte_ersetzen(s, b: Bestand) -> dict:
    """Volle Namen, Adressen und Telefonnummern in FREMDEN Texten ersetzen.

    Regeln (Fachentscheidung K2, R-DSGVO-1):

    * Nur der VOLLE Name („Vorname Nachname“, „Nachname, Vorname“), die
      Mail-Adresse und die Telefonnummer — als GANZES WORT, Groß/klein egal.
    * Der übrige Text bleibt in seiner Originalschreibung (keine
      `lower()`-Ersetzung über die ganze Spalte).
    * Wohnort, PLZ, Straße und einzelne Vornamen werden NICHT angefasst:
      „Eva“ träfe sonst „Evangelisch“, „Ben“ träfe „Benutzer“.

    Eigene Zeilen sind zu diesem Zeitpunkt bereits geleert; was hier noch
    steht, gehört anderen Personen.
    """
    spalten = _fremdtext_spalten()
    muster = [(n, _muster(n)) for n in b.fremd_nadeln if len(n) >= 3]
    if not muster:
        return {}
    zaehler: dict[str, int] = {}
    # Ein Katalog-Lesevorgang fuer die ganze Schleife (nicht einer je Tabelle).
    # ``None`` = Katalog nicht lesbar: dann wird NICHT gefiltert. Ein leerer
    # Ersatz (`set()`) uebersprang JEDE Tabelle — die Ersetzung lief still ins
    # Leere, und der Vollscan meldete trotzdem 0 Treffer (fail open).
    vorhanden = _vorhandene_tabellen(s)
    for tabelle in _tabellen():
        # Eine Tabelle, die es in DIESER Datenbank nicht gibt (ID-1f:
        # `id1_mitglied_kennung` nach einem Downgrade), kann auch keinen Text
        # tragen — `_vorhandene_tabellen` fragt ueber die GEHALTENE Verbindung,
        # ein `inspect().has_table()` wuerde den SAVEPOINT des Aufrufers
        # mitreissen. Eine Abfrage auf eine fehlende Tabelle scheitert und
        # rollt die Transaktion zurueck: deshalb der Filter.
        if vorhanden is not None and tabelle.name not in vorhanden:
            continue
        for spalte in tabelle.c:
            if not isinstance(spalte.type, (String, Text)):
                continue
            if (tabelle.name, spalte.name) not in spalten:
                continue
            pk = list(tabelle.primary_key.columns)
            if not pk:
                continue
            for zeile in s.execute(select(*pk, spalte)).all():
                *schluessel, wert = zeile
                if not wert:
                    continue
                neu, anzahl = _ersetze_text(str(wert), muster)
                if not anzahl:
                    continue
                bedingung = and_(*[c == w for c, w in zip(pk, schluessel)])
                s.execute(update(tabelle).where(bedingung).values({spalte.key: neu}))
                schluessel_name = f"{tabelle.name}.{spalte.name}"
                zaehler[schluessel_name] = zaehler.get(schluessel_name, 0) + anzahl

    # NACHWEIS (R-DSGVO-1b, Restliste 7): dieselben Regeln gelten IN den
    # JSON-Spalten. `_verweise_umhaengen` hat vorher GENAU die Klarname-Werte
    # auf die Kennung gehängt; was hier übrig bleibt, ist ein FREMDER
    # Langtext, der den Namen als ganzes Wort nennt — z. B. die
    # Anmeldungsliste in `dm_befund.element`. Schlüssel des JSON bleiben
    # unangetastet, genauso wie der Wert-Vergleich von N-2 (Konto-Mails)
    # weiterhin über die ganze Zeile läuft.
    for tabelle_name, json_spalten in WERT_SPALTEN.items():
        tabelle = _tabelle(tabelle_name)
        if tabelle is None:
            continue
        pk = list(tabelle.primary_key.columns)
        if not pk:
            continue
        for spaltenname, art in json_spalten.items():
            if art != "json":
                continue
            spalte = tabelle.c.get(spaltenname)
            if spalte is None:
                continue
            schluessel_name = f"{tabelle_name}.{spaltenname}"
            for zeile in s.execute(select(*pk, spalte)).all():
                *schluessel, wert = zeile
                if wert is None:
                    continue
                neu, anzahl = _json_text_ersetzen(wert, muster)
                if not anzahl:
                    continue
                bedingung = and_(*[c == w for c, w in zip(pk, schluessel)])
                s.execute(update(tabelle).where(bedingung).values({spalte.key: neu}))
                zaehler[schluessel_name] = zaehler.get(schluessel_name, 0) + anzahl
    return zaehler


def _json_text_ersetzen(wert, muster) -> tuple[object, int]:
    """Wie `_json_ersetzen`, aber als GANZES WORT in JEDEM String-Wert.

    Nur Werte, nicht Schlüssel: ein JSON-Pfad wie `data-v-b033fc25` gehört
    zum Gerüst, nicht zum Inhalt.
    """
    if isinstance(wert, str):
        return _ersetze_text(wert, muster)
    if isinstance(wert, list):
        neu, anzahl = [], 0
        for teil in wert:
            neu_wert, n = _json_text_ersetzen(teil, muster)
            neu.append(neu_wert)
            anzahl += n
        return neu, anzahl
    if isinstance(wert, dict):
        neu, anzahl = {}, 0
        for schluessel, teil in wert.items():
            neu_wert, n = _json_text_ersetzen(teil, muster)
            neu[schluessel] = neu_wert
            anzahl += n
        return neu, anzahl
    return wert, 0


def _eigene_schluessel_ersetzen(s, b: Bestand, kennung: str) -> dict:
    """Schlüssel EIGENER Nachweiszeilen auf die neutrale Kennung (ID-1f).

    Im Betrieb heißt der Einwilligungs-Nachweis „DSGVO-<Kennung>-0114“
    (`frappe_compat/api_helpers._new_name`), im Altbestand stand dort der
    Klarname („DSGVO-Elvira Dorn-0114“, N3/R-ID-1). Die Zeile muss bleiben
    (Art. 7) — ihr SCHLÜSSEL darf die Person aber nicht führen, sonst meldet der
    Vollscan sie als Rest.

    ZWEI Schritte, in dieser Reihenfolge:

    1. **Kennungsregel** (`_schluessel_neu`): Präfix aus `EINWILLIGUNG_PRAEFIXE`,
       danach der Namensanteil GENAU eine Kennung der Person (aktuelle, neue
       ODER frühere aus `id1_mitglied_kennung`), danach eine laufende Nummer.
       Der Namensanteil wird die neutrale Kennung, die Nummer bleibt. Dieselbe
       Regel wie die Migration (`id1_mitglied_kennungen._einwilligung_neu`).
    2. **Klarnamen-Suche** (die Regel von vor ID-1, `_ersetze_text` mit
       `b.fremd_nadeln`): sie trifft die Fälle, die die Bauform NICHT ist —
       `DSGVO-<Name>-0114-1` (Kollisionszusatz), Altzeilen ohne Eintrag in der
       Abbildung und Zeilen, deren Kennung eine andere ist. Der Name wird wie in
       fremden Texten ersetzt (`FREITEXT_ERSETZUNG`), die laufende Nummer bleibt.

    Nur eigene Zeilen (`mitglied`), nie ein Teilstring — eine Zeile zu einer
    anderen Person bleibt unangetastet. Für Schritt 2 heißt das: `mitglied`
    steht auf einer Kennung der Person ODER die Zeile trägt gar keine Kennung
    (kennungslose Altzeile aus der Zeit vor ID-1). Eine Nachweiszeile einer
    ANDEREN Person schreibt die Löschung nicht um — auch dann nicht, wenn sie
    denselben Namen trägt; das wäre deren Nachweis (Art. 7), nicht unserer.

    Läuft NACH der Umhängung, also bevor die Einwilligungs-Zeilen der Person
    über `kennung` gefunden werden; die früheren Kennungen stehen im Bestand.
    """
    zaehler: dict[str, int] = {}
    tabelle = _tabelle("dsgvo_einwilligung")
    if tabelle is None or tabelle.c.get("mitglied") is None:
        return zaehler
    schluessel = list(tabelle.primary_key.columns)
    if not schluessel:
        return zaehler
    spalte = schluessel[0]
    kennungen = set(b.kennungen) | {b.mitglied}
    kennungen.discard("")
    # EIGENE Zeilen: der Bezug `mitglied` steht auf der alten, der neuen oder
    # einer früheren Kennung der Person.
    eigene_kennungen = set(kennungen) | {kennung}
    eigene = tabelle.c["mitglied"].in_(eigene_kennungen)
    # Klarnamen-Suche (Schritt 2): die Regel von vor ID-1.
    muster = [(n, _muster(n)) for n in b.fremd_nadeln if len(n) >= 3]
    # Schon beruecksichtigt: was die Kennungsregel umschreibt, ist erledigt;
    # der zweite Schritt soll nicht denselben Schlüssel ein zweites Mal fassen.
    erledigt: set[str] = set()
    if kennungen:
        # Reihenfolge fest: Schluessel der Bauform zuerst (Kennungsregel),
        # danach die uebrigen — sonst entschiede die Reihenfolge des Scans,
        # welche Regel einen Kollisionsschluessel fuer sich beansprucht.
        vorhandene = sorted(
            (str(a or "") for a in s.scalars(select(spalte).where(eigene)).all()),
            key=lambda s_: (_schluessel_neu(s_, kennungen, kennung) is None, s_))
        for alt in vorhandene:
            neu = _schluessel_neu(str(alt or ""), kennungen, kennung)
            if neu is None or neu == alt:
                continue
            erledigt.add(str(alt))
            _schluessel_umbenennen(s, tabelle, spalte, alt, neu)
            zaehler["dsgvo_einwilligung.name"] = (
                zaehler.get("dsgvo_einwilligung.name", 0) + 1)
    # Schritt 2: Klarname im Schlüssel, wo die Bauform nicht passt — nur in
    # EIGENEN Zeilen. `mitglied` zeigt auf eine Kennung der Person, oder die
    # Zeile führt keine Kennung (Altzeile aus der Zeit vor ID-1; die Migration
    # hat dort einen LEEREN Wert eingetragen, keine fremde Kennung). Der
    # Klarname im Schlüssel ist Personendatum — aber nur das der Person, deren
    # Antrag gerade vollzogen wird. Ersetzt wird ausschließlich der Wortlaut
    # der PERSON (`b.fremd_nadeln`, volle Namen).
    if not muster:
        return zaehler
    eigene_zeilen = or_(eigene, tabelle.c["mitglied"].is_(None),
                        tabelle.c["mitglied"] == "")
    for alt in sorted(str(a or "") for a in s.scalars(
            select(spalte).where(eigene_zeilen)).all()):
        if not alt or alt in erledigt:
            continue
        # Gehoert der Schluessel der Kennungsregel? Dann traegt er eine Kennung
        # der Person und KEINEN Namen — dort stuende die neutrale Kennung.
        if not any(rx.search(alt) for _n, rx in muster) and _nennt_kennung(
                alt, kennungen):
            continue
        neu, anzahl = _ersetze_text(str(alt), muster)
        if not anzahl or neu == alt:
            continue
        _schluessel_umbenennen(s, tabelle, spalte, alt, neu)
        zaehler["dsgvo_einwilligung.name"] = (
            zaehler.get("dsgvo_einwilligung.name", 0) + anzahl)
    return zaehler


def _nennt_kennung(schluessel: str, kennungen) -> bool:
    """Traegt `schluessel` nach einem Praefix GENAU eine Kennung der Person?

    Dieselbe Bauform wie `_schluessel_neu`, aber ohne die laufende Nummer —
    danach sucht die Kennungsregel, alles andere ist Fall der Namenssuche.
    """
    for praefix in EINWILLIGUNG_PRAEFIXE:
        if schluessel.startswith(praefix):
            stamm = schluessel[len(praefix):]
            return any(stamm == k or stamm.startswith(k + "-") for k in kennungen)
    return False


def _schluessel_umbenennen(s, tabelle, spalte, alt: str, neu: str) -> None:
    """Schlüssel `alt` -> `neu` umschreiben; Kollisionen bekommen einen Zusatz.

    Zwei Personen dürfen nach der Ersetzung nicht denselben Schlüssel bekommen
    (`DSGVO-<Kennung>-0114` könnte schon stehen) — dann wird eine Laufnummer
    angehängt, der Schlüssel bleibt eindeutig.
    """
    kandidat, nr = neu, 0
    while s.execute(select(spalte).where(spalte == kandidat)).first() is not None:
        nr += 1
        kandidat = f"{neu}-{nr}"
    s.execute(update(tabelle).where(spalte == alt).values({spalte.key: kandidat}))


def _schluessel_neu(alt: str, kennungen: set[str], kennung: str) -> str | None:
    """Neuer Schlüssel eines Nachweises — ``None``, wenn die Form nicht passt.

    Aufbau: ``<Präfix><Namensanteil>-<laufende Nummer>``. Der Namensanteil muss
    GENAU eine Kennung der Person sein, die Nummer aus Ziffern bestehen (also
    NICHT die Form mit Kollisionszusatz `-0114-1` — die trifft der zweite
    Schritt von `_eigene_schluessel_ersetzen`). Alles andere (Altzeilen ohne
    Kennung, Zeilen zu fremden Dokumenten) bleibt, wie es ist.
    """
    for praefix in EINWILLIGUNG_PRAEFIXE:
        if not alt.startswith(praefix):
            continue
        stamm, trenner, nummer = alt[len(praefix):].rpartition("-")
        if not trenner or not nummer.isdigit():
            continue
        if stamm in kennungen:
            return f"{praefix}{kennung}-{nummer}"
    return None


def _ersetze_text(text_: str, muster) -> tuple[str, int]:
    """Ersetzt alle Treffer; gibt (neuer Text, Anzahl) zurück."""
    anzahl = 0
    ergebnis = text_
    for _nadel, rx in muster:
        ergebnis, treffer = rx.subn(FREITEXT_ERSETZUNG, ergebnis)
        anzahl += treffer
    return ergebnis, anzahl


#: Spalten, in denen die Person in FREMDEN Texten stehen kann: Freitext- und
#: Namensspalten aus dem Inventar (`protokoll`, `fremd`) sowie die übrigen
#: Textspalten der Metadaten, die KEIN Schlüssel und KEIN Verweis sind. Die
#: Liste wird zur Laufzeit ergänzt (`_fremdtext_spalten()`), damit eine neue
#: Notiz-/Beschreibungsspalte nicht still durchrutscht.
_FREMDTEXT_SPALTEN: set[tuple[str, str]] = set()

#: Spalten, die NIE im Klartext ersetzt werden: Schlüssel, Hashes, Verweise,
#: Geräteangaben. `owner`/`created_by`/`modified_by` tragen den KONTOnamen und
#: werden zentral genullt (`_konto_verweise_aufloesen`).
_NICHT_TEXT = frozenset({
    "name", "parent", "parenttype", "parentfield", "owner", "modified_by",
    "created_by", "password_hash", "token_hash", "slug", "user", "actor",
    "for_user", "from_user", "nutzer", "benutzer", "mitglied", "target_user",
    "target_name", "target_doctype", "content_hash", "issuer", "sub",
    "file_url", "datei", "bild", "foto", "screenshot", "version_num",
    "schluessel", "plantyp", "gruppe_id", "plan", "termin", "sammlung",
    "merkmal", "link_name", "reference_docname", "document_name",
    "document_type", "ip_adresse", "ip_address", "user_agent", "status",
    "email", "email_freitext", "name_freitext", "telefon", "vorname",
    "nachname", "autor", "autor_email", "beziehung_zu", "verantwortlicher",
    "leitung", "teilnehmer", "zugeteilt_von", "erstellt_von", "created_by",
    "referenz_name", "quelle_name", "inhalt_name", "attached_to_name",
    "moderiert_von", "gebucht_von", "gebucht_von_name", "ziel_id", "bezug",
    "dateiname", "file_name", "attached_to_doctype", "referenz_doctype",
    "quelle_doctype", "inhalt_doctype", "link_doctype", "doctype",
    "parent_doctype", "role", "route", "url", "pfad", "aktion", "typ",
    # N-6: `user.full_name` ist der Anzeigename EINES Kontos. Ein anderes Konto
    # mit demselben Vollnamen (Namensvetter) behält seinen Namen; das Konto der
    # gelöschten Person wird ohnehin gelöscht.
    "full_name",
})


def _fremdtext_spalten() -> set[tuple[str, str]]:
    """Alle Textspalten, in denen fremde Personen im Fließtext stehen können."""
    if _FREMDTEXT_SPALTEN:
        return _FREMDTEXT_SPALTEN
    for tabelle in _tabellen():
        for spalte in tabelle.c:
            if not isinstance(spalte.type, (String, Text)):
                continue
            if spalte.primary_key or spalte.name in _NICHT_TEXT:
                continue
            if any(fk.target_fullname for fk in spalte.foreign_keys):
                continue
            _FREMDTEXT_SPALTEN.add((tabelle.name, spalte.name))
    return _FREMDTEXT_SPALTEN


def _eigene_dateien(s, b: Bestand, kennung: str) -> dict:
    """Datei-Verweise der Person einsammeln und die Spalten leeren.

    Die Dateien selbst werden NACH dem Commit physisch entfernt
    (`dateien_entfernen`) — ein Rollback darf keine Datei gelöscht haben.
    """
    zaehler: dict[str, int] = {}
    # `file`-Anhänge am Mitglied (Ausweis-PDF usw.): Namen einsammeln und die
    # ZEILEN löschen (N-3) — `file_name` trägt den Klarnamen („Ausweis Elvira
    # Dorn.pdf“), die Datei selbst fällt nach dem Commit.
    datei = _tabelle("file")
    eigene_dateien = []
    if datei is not None and datei.c.get("attached_to_name") is not None:
        spalte_url = datei.c.get("file_url")
        bedingung = and_(
            datei.c.get("attached_to_doctype") == "Mitglied",
            datei.c["attached_to_name"].in_([b.mitglied, kennung]),
        )
        for zeile in s.execute(select(datei.c["name"], spalte_url).where(bedingung)).all():
            eigene_dateien.append(zeile[0])
            if zeile[1]:
                b.dateien.add(str(zeile[1]))
        if eigene_dateien:
            _zaehle(s, zaehler, "file", delete(datei)
                    .where(datei.c["name"].in_(eigene_dateien)))
    # `sicherer_anhang.datei` und `bug_report.screenshot`: Spalte leeren, Pfad
    # merken (die Zeilen selbst fallen über `ZEILEN_LOESCHEN` bzw. bleiben mit
    # neutralem Inhalt).
    for tabelle_name, spaltenname in (("sicherer_anhang", "datei"),
                                      ("bug_report", "screenshot")):
        tabelle = _tabelle(tabelle_name)
        if tabelle is None or tabelle.c.get(spaltenname) is None:
            continue
        spalte = tabelle.c[spaltenname]
        bedingungen = []
        if tabelle.c.get("mitglied") is not None:
            bedingungen.append(tabelle.c["mitglied"].in_([b.mitglied, kennung]))
        if b.konten and tabelle.c.get("benutzer") is not None:
            bedingungen.append(tabelle.c["benutzer"].in_(b.konten))
        if not bedingungen:
            continue
        if tabelle_name == "sicherer_anhang":
            # N-3: die Zeile fällt in `_zeilen_loeschen` (Art. 9-Freitext im
            # Dateinamen). Hier nur noch den PFAD einsammeln, bevor sie weg ist.
            for wert in s.scalars(select(spalte).where(or_(*bedingungen))).all():
                if wert:
                    b.dateien.add(str(wert))
            continue
        for wert in s.scalars(select(spalte).where(or_(*bedingungen))).all():
            if wert:
                b.dateien.add(str(wert))
        _zaehle(s, zaehler, f"{tabelle_name}.{spaltenname}", update(tabelle)
                .where(and_(or_(*bedingungen), spalte.is_not(None)))
                .values({spalte.key: None}))
    return zaehler


def _pruefe_konsistenz(s) -> None:
    """Flusht die Sitzung — hier treten FK-/Constraint-Fehler auf.

    Bewusst VOR dem Mailversand (K3): eine Mail „deine Daten werden jetzt
    gelöscht“ darf nicht rausgehen, wenn die Löschung danach am Fremdschlüssel
    scheitert. Der Aufrufer rollt bei einem Fehler zurück; das ist gefahrlos,
    weil noch nichts committet ist.
    """
    s.flush()


def _platzhalter_aufloesen(s) -> dict:
    """Verweise auf `GELOESCHTES_KONTO` auf NULL setzen.

    Das Platzhalter-Konto ist ein Verweis-ZIEL, keine Person: es wird nie
    angelegt. Zeigt eine Zeile darauf, ist der Bezug ohnehin leer — ein NULL
    sagt das ehrlich, und die Zeile bleibt.
    """
    zaehler: dict[str, int] = {}
    for tabelle in _tabellen():
        for spalte in tabelle.c:
            if not isinstance(spalte.type, (String, Text)):
                continue
            if spalte.name not in _KONTO_SPALTEN:
                continue
            _zaehle(s, zaehler, f"{tabelle.name}.{spalte.name}", update(tabelle)
                    .where(spalte == GELOESCHTES_KONTO).values({spalte.key: None}))
    return zaehler


#: Spalten, die ein KONTO nennen können (Name des Kontos = E-Mail).
_KONTO_SPALTEN = frozenset({
    "user", "benutzer", "nutzer", "actor", "for_user", "from_user", "target_user",
})


def _zaehle(s, zaehler: dict, schluessel: str, anweisung) -> None:
    ergebnis = s.execute(anweisung)
    anzahl = int(ergebnis.rowcount or 0)
    if anzahl:
        zaehler[schluessel] = zaehler.get(schluessel, 0) + anzahl


def dateien_entfernen(pfade) -> int:
    """Löscht Dateien aus `FILES_DIR` (nach dem Commit der Anonymisierung).

    Nur innerhalb von `settings.files_dir` — ein Pfad aus der Datenbank darf
    niemals außerhalb des Dateispeichers wirken. Fehler werden gesammelt und
    gemeldet, nicht geworfen: die Anonymisierung ist zu diesem Zeitpunkt
    bereits committet, und ein fehlendes Bild ist kein Grund, den Vorgang als
    gescheitert darzustellen.
    """
    import os

    from diakronos_app.files import stored_path
    from diakronos_app.settings import get_settings

    basis = os.path.realpath(str(get_settings().files_dir or "/data/files"))
    entfernt = 0
    for pfad in pfade or ():
        # `stored_path` prüft Name, Symlink und Wurzel — dieselbe Schranke wie
        # beim Ausliefern einer Datei.
        try:
            ziel = stored_path(os.path.basename(str(pfad)))
        except Exception:  # noqa: BLE001 — unbekannter Verweis ist kein Fehlerfall
            continue
        if ziel is None:
            continue
        echt = os.path.realpath(str(ziel))
        if not echt.startswith(basis + os.sep):
            continue
        try:
            os.unlink(echt)
            entfernt += 1
        except OSError:
            continue
    return entfernt


# ── Inventar-Arten → Code ───────────────────────────────────────────────────
#
# Jede Art aus `SPALTEN` ist hier einer Funktion zugeordnet, die sie ausführt.
# `test_dsgvo1_inventar.py::test_jede_inventar_art_ist_implementiert` prüft,
# dass keine benutzte Art fehlt (N-4, R-DSGVO-1b: `mitglied_platzhalter` und
# nicht-FK-`user_null` waren bis dahin toter Buchstabe).
INVENTAR_ARTEN.update({
    # FK/Verweis auf die Person: Schritt 3 (`_verweise_umhaengen`).
    "mitglied": _verweise_umhaengen,
    # Selbstbezug der Person: Schritt 1 (in `anonymisiere`).
    "mitglied_null": anonymisiere,
    # Identität der NEUEN Zeile: `_mitglied_werte()` in `_neue_zeile`.
    "mitglied_werte": _neue_zeile,
    # Kennung/Name ohne FK (Bucher in `ressourcen_buchung`).
    "mitglied_platzhalter": _platzhalter_spalten,
    # Konto-Verweise: `_konto_verweise_aufloesen` (FK und Inventar ohne FK).
    "user_null": _konto_verweise_aufloesen,
    "user_platzhalter": _konto_verweise_aufloesen,
    # Datei der Person: `_dateipfade_sammeln` + `dateien_entfernen`.
    "eigene_datei": _eigene_dateien,
    # Nachweis (Art. 17/7) bleibt stehen, nur der Bezug ist die Kennung.
    "keep": _verweise_umhaengen,
    # ID-1f: Schlüssel einer eigenen Zeile (Einwilligung), der die Kennung der
    # Person trägt — wird umgeschrieben, nicht geleert.
    "eigene_kennung": _eigene_schluessel_ersetzen,
    # Eigene Protokollzeilen: `_eigene_protokolle` / `_benachrichtigungen_...`.
    "protokoll": _eigene_protokolle,
    # Fremdtext: `_fremdtexte_ersetzen` (nur VOLLE Namen, Adressen, Telefon).
    "fremd": _fremdtexte_ersetzen,
    # Zeile verschwindet: `_zeilen_loeschen`.
    "zeile_loeschen": _zeilen_loeschen,
    # Komma-Liste (BACKUP-1 `sicherungslauf.benachrichtigt`): Eintrag exakt
    # entfernen — `_konto_listen_bereinigen`.
    "liste": _konto_listen_bereinigen,
    # Strukturspalte (Sicherungs-Protokoll): beschreibt den LAUF, nicht eine
    # Person — nichts zu löschen (`_nichts_zu_tun`).
    "struktur": _nichts_zu_tun,
})
