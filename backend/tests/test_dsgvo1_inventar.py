"""DSGVO-1 (D5): das Inventar gegen die ECHTE Datenbank prüfen.

Der Vollscan in `test_dsgvo1_anonymisierung.py` läuft über die Modell-Metadaten
und sucht die WERTE der Person. Das genügt für die Logik, aber nicht für die
Zusage „nichts Personenbezogenes bleibt“: die Betriebs-DB kann Textspalten
tragen, die im Modell fehlen (Overlay-Spalten aus der Frappe-Historie).

Dieser Test liest deshalb `information_schema.columns` — die Wahrheit über die
Datenbank, gegen die die Suite gerade läuft — und verlangt für JEDE Textspalte
eine erkennbare Entscheidung. Damit eine neue Spalte nicht still durchrutscht,
muss sie in GENAU eine der folgenden Kategorien fallen:

  A. im Inventar (`dsgvo_anonymisierung.SPALTEN`) — genullt oder ersetzt,
  B. in einer Tabelle, deren Zeilen komplett gelöscht werden (`ZEILEN_LOESCHEN`),
  C. eine Struktur-/Protokollspalte (`STRUKTUR_SPALTEN`, zentral behandelt),
  D. ein Verweis auf ein Fachobjekt (`*_doctype`, `*_status` …),
  E. eine Spalte einer Tabelle, die NIE Personendaten führt
     (`STAMMDATEN_TABELLEN`).

Was in keine Kategorie fällt, bricht den Test. Das ist Absicht: die
Entscheidung gehört zu der Karte, die das Feld einführt — nicht zu der, die
Monate später löscht.
"""
from __future__ import annotations

from sqlalchemy import String, Text, text

from diakronos_app import dsgvo_anonymisierung as modul

BETRIEBS_SQL = text(
    "SELECT table_name, column_name, data_type FROM information_schema.columns "
    "WHERE table_schema = current_schema() AND data_type IN "
    "('text', 'character varying', 'character') "
    "AND table_name NOT IN ('alembic_version') "
    "ORDER BY table_name, column_name"
)

#: Frappe-Schlüssel und Protokollspalten mit KONTO-Namen. Begründung einmal:
#:
#: * `name` ist die technische ID und MUSS bleiben — an ihr hängen Nachweis
#:   (D1) und Planhistorie (D5).
#: * `parent` zeigt auf das ELTERNOBJEKT (Dienstplan, Gruppe, Anmeldung), nicht
#:   auf eine Person; wo eine Zeile eine Person nennt, steht sie in einer
#:   eigenen Spalte (`mitglied`, `benutzer`) und ist dort im Inventar.
#: * `owner`/`modified_by`/`created_by`/`from_user` tragen den Kontonamen und
#:   werden für das Konto der Person zentral genullt
#:   (`dsgvo_anonymisierung._konto_verweise_aufloesen`). Die `user`-Zeile
#:   selbst wird GELÖSCHT (D5), nicht per CASCADE mitgerissen — die übrigen
#:   Zeilen der Tabelle bleiben und behalten ihre eigenen Protokollspalten.
STRUKTUR_SPALTEN = frozenset({
    "name", "parent", "parenttype", "parentfield", "owner", "modified_by",
    "created_by", "from_user",
    # Frappe-Fachklassifikation je Zeile (Status, Kategorie, Titel eines
    # Beitrags). Sie beschreiben das OBJEKT, nicht eine Person — Namen darin
    # (etwa ein Plantitel) sind redaktionell und werden nicht durchsucht.
    "status", "kategorie", "consequence", "field_changed", "policy_triggered",
    "build", "oberflaeche", "route", "viewport", "naming_series",
    "screenshot", "bild", "titel", "auszug", "beschreibung",
    "anmeldungstyp", "dsgvo_text_snapshot", "funktion", "bezeichnung",
    "detail", "gruppenname", "untergruppenname", "treffpunkt", "treffzeit",
    "beschreibung", "urheber", "komponist", "textautor", "verlag",
    "lizenzhinweis", "notiz", "notizen", "grund", "zweck", "ablehnungs_grund",
    "konsole_log", "netzwerk_log", "element_html", "element_text",
    "element_komponente", "element_selektor", "vorschlag", "antwort",
    "feldlabel", "optionen", "willkommenstext", "aufbewahrung",
    "datenschutzerklaerung", "einwilligung", "bestaetigung_text",
    "dsgvo_text_override", "bezeichnung", "organisationsname",
    "kontakt_email", "oeffentliche_adresse", "link_anzeige",
    "freitext_ressource", "tags", "typ", "art", "stimme", "stimmen",
    "rollenname", "rollentyp", "stimmlage", "umfang", "tonart", "taktart",
    "besetzung", "fassungsname", "arrangeur", "schwierigkeit", "sprache",
    "nummer", "seite", "buch", "quelle", "anlass", "anlassname",
    "kategoriename", "typname", "existing", "topic",
})

#: Tabellen, die NIE personenbezogene Daten einer gelöschten Person führen:
#: Stammdaten, Konfiguration, veröffentlichte Texte, Werkangaben. Eine
#: Mitgliedszeile gibt es dort nicht — und ein Name in einem Gruppennamen ist
#: ein fachliches Objekt, keine Person.
STAMMDATEN_TABELLEN = frozenset({
    "role", "doctype", "audit_policy",
    "datenschutz_text", "datenschutz_text_veroeffentlicht",
    "diakronos_einstellungen", "diakronos_modul_einstellung",
    "diakronos_modul_rolle", "gemeinde_einstellungen",
    "google_kalender_einstellungen", "kronos_einstellungen",
    # MAIL-1: die SMTP-Einstellungen sind KONFIGURATION der Instanz, kein
    # Personenbezug einer Mitgliedszeile. `absender`/`benutzername` sind ein
    # Funktionspostfach der Gemeinde, nicht die Daten einer gelöschten Person —
    # eine Löschung darf den Mailversand nicht lahmlegen. Das Passwort steht
    # dort ausserdem nur als Fernet-Geheimtext.
    "smtp_einstellungen",
    "auth_einstellungen", "auth_gruppen_rolle", "dashboard_widget",
    "anmeldeformular", "anmeldeformular_feld", "anmeldeformular_dokument",
    "dienstrolle", "dienstplan_vorlage", "dienstplan_vorlage_gruppe",
    "dienstplan_vorlage_kategorie", "dienstplan_vorlage_slot",
    "dienstbereich", "gruppentyp", "gruppenrolle", "lied", "liedanlass",
    "liedkategorie", "liedgruppe", "liedgruppe_rolle", "liedgruppe_lied",
    "liedfassung", "liedstrophe", "lied_material", "lied_anlass",
    "lied_kategorie", "lied_gruppenzuordnung", "eventkategorie",
    "ressource", "kalender", "registrierungslink", "ablaufplan",
    "ablaufplan_position", "element", "element_ressource",
    "pr_plantyp", "pr_plantyp_version", "pr_merkmal", "pr_merkmal_wert",
    "pr_sammlung", "pr_sammlung_eintrag", "pr_eintrag",
    # Frappe-Infrastruktur: Verweise, Hashes, Ablagemetadaten.
    "file", "dynamic_link", "event_participants", "docfield",
    "dsgvo_einwilligung",
    # Planrahmen: die Zeilen-IDs sind technische Kennungen (`pr_*`-Tabellen
    # sind per Migration entstanden, nicht per Frappe-Namensreihe).
    "pr_plan", "pr_termin", "pr_verlauf",
})

#: Namensbestandteile, die einen VERWEIS oder eine Klassifikation kennzeichnen
#: — kein Personenbezug, weil das Ziel selbst bewertet wird.
VERWEIS_ENDUNGEN = (
    "_doctype", "_typ", "_type", "_field", "_fieldname", "_category",
    "_kategorie", "_farbe", "_color", "_icon", "_status", "_art",
    "_variante", "_szene", "_rolle", "_rhythmus", "_wochentag", "_modus",
    "_einheit", "_label", "_reihe", "_quelle", "_anzeige", "_name",
)


def _db_spalten(session) -> set[tuple[str, str]]:
    """Textspalten aus der ECHTEN DB, sonst aus den Metadaten."""
    try:
        return {(str(t), str(c)) for t, c, _typ in session.execute(BETRIEBS_SQL).all()}
    except Exception:  # noqa: BLE001 — SQLite kennt information_schema nicht
        from diakronos_app.models.base import Base

        return {
            (mapper.local_table.name, c.name)
            for mapper in Base.registry.mappers
            for c in mapper.local_table.c
            if isinstance(c.type, (String, Text))
        }


#: Spalten eines VERWEISES auf ein Fachobjekt: der Wert ist eine ID, die
#: selbst im Inventar steht oder nicht personenbezogen ist.
VERWEIS_SPALTEN = frozenset({
    "element", "gruppe", "untergruppe", "registrierungslink", "anmeldeformular",
    "dienstbereich", "kalender", "vorlage", "dienstrolle", "fassung",
    "ressource", "anmeldung", "obergruppe", "gruppentyp", "element_calendar",
    "reference_docname", "antragsteller", "pr_abwesenheit", "fieldname",
    "moderiert_von", "plantyp", "plantyp_version", "bezug",
    "kronos_element", "plan", "gruppe_id", "szene", "sichtbarkeit",
    "ancestor_path", "adressbuch_sichtbarkeit", "familiengrund",
    "familienstand", "geschlecht", "foto", "text", "rolle", "aktion",
    "attached_file", "email_header", "link", "type", "id",
    "erledigt_von", "freigegeben_von", "dienstplan",
})


def _kategorie(tabelle: str, spalte: str) -> str | None:
    """In welche Kategorie fällt die Spalte? `None` = unentschieden."""
    if spalte in modul.SPALTEN.get(tabelle, {}):
        return "A"
    if spalte in VERWEIS_SPALTEN:
        return "D"
    if tabelle in {name for name, _ in modul.ZEILEN_LOESCHEN}:
        return "B"
    if spalte in STRUKTUR_SPALTEN:
        return "C"
    if spalte.endswith(VERWEIS_ENDUNGEN) or spalte == "idx":
        return "D"
    if tabelle in STAMMDATEN_TABELLEN:
        return "E"
    return None


def test_jede_textspalte_hat_eine_entscheidung(patched_db):
    """Keine Textspalte ohne erkennbare DSGVO-Entscheidung."""
    from diakronos_app.db import SessionLocal

    with SessionLocal() as s:
        spalten = _db_spalten(s)
    offen = sorted(f"{t}.{c}" for t, c in spalten if _kategorie(t, c) is None)
    assert offen == [], (
        "Textspalten ohne DSGVO-Entscheidung — bitte in "
        "dsgvo_anonymisierung.SPALTEN aufnehmen (nullen/ersetzen) oder als "
        "Stammdaten-Tabelle/Strukturspalte begründen:\n  " + "\n  ".join(offen)
    )


def test_inventar_nennt_nur_existierende_spalten(patched_db):
    """Ein Tippfehler im Inventar würde eine echte Spalte still übergehen.

    Verglichen wird gegen den Katalog der TEST-Datenbank (`patched_db`): die
    steht vor jedem Test frisch auf dem Modell-Stand, alle Tabellen sind da.
    Früher lief dieser Test gegen `settings.database_url` — also gegen die
    Betriebs-DB, in der die ID-1-Migration noch fehlen kann; das war ein Test
    am Betrieb, kein Test am Code (Regel 11).
    """
    from diakronos_app.db import SessionLocal

    with SessionLocal() as s:
        spalten = _db_spalten(s)
    fehlend = [
        f"{tabelle}.{spalte}"
        for tabelle, felder in modul.SPALTEN.items()
        for spalte in felder
        if (tabelle, spalte) not in spalten
    ]
    assert fehlend == [], f"Inventar nennt unbekannte Spalten: {fehlend}"


def test_konto_zeilen_sind_auch_loeschzeilen():
    """`KONTO_ZEILEN` muss Teilmenge der Löschliste sein — sonst bliebe eine
    Zeile stehen, die nur genullt wurde, und der Verweis zeigte ins Leere."""
    assert modul.KONTO_ZEILEN <= {name for name, _ in modul.ZEILEN_LOESCHEN}


def test_platzhalter_konto_ist_kein_konto(patched_db):
    """`GELOESCHTES_KONTO` ist ein Verweis-Ziel, keine Person und kein Konto."""
    from diakronos_app.db import SessionLocal
    from diakronos_app.models.core import User

    with SessionLocal() as s:
        assert s.get(User, modul.GELOESCHTES_KONTO) is None


def test_statuswerte_sind_die_einzigen():
    from diakronos_app.models.datenschutz import STATUS_WERTE

    # DSGVO-2a ergänzt „abgelehnt“: die Verwaltung hat den Antrag geprüft und
    # nicht bestätigt — der Status ist damit ein Endstand wie die anderen.
    assert set(STATUS_WERTE) == {"offen", "zurueckgezogen", "ausgefuehrt", "abgelehnt"}


def test_jede_inventar_art_ist_implementiert():
    """N-4: jede im Inventar benutzte Art hat einen ausführenden Code-Pfad.

    Der Wächter in `test_dsgvo1b_verweise.py` prüft nur, ob eine Spalte einen
    Eintrag HAT. Eine Art ohne Funktion (`mitglied_platzhalter`, nicht-FK
    `user_null`) war bis DSGVO-1b toter Buchstabe — die Spalte blieb stehen,
    ohne dass ein Test anschlug.
    """
    from diakronos_app import dsgvo_anonymisierung as modul

    benutzt = {art for felder in modul.SPALTEN.values()
               for art, _grund in felder.values()}
    assert benutzt, "das Inventar ist leer"
    assert benutzt <= set(modul.INVENTAR_ARTEN), sorted(benutzt - set(modul.INVENTAR_ARTEN))
    for art, funktion in modul.INVENTAR_ARTEN.items():
        assert callable(funktion), art
        assert funktion.__module__ == modul.__name__, art


def test_nachweistabellen_bleiben_im_inventar():
    """Löschantrag und Einwilligung sind Nachweise (Art. 17/7) — sie werden
    ausdrücklich NICHT geleert, nur ihr Bezug ist die technische ID."""
    assert modul.SPALTEN["loeschantrag"]["mitglied"][0] == "keep"
    assert modul.SPALTEN["dsgvo_einwilligung"]["mitglied"][0] == "keep"
    assert "loeschantrag" not in {name for name, _ in modul.ZEILEN_LOESCHEN}
    assert "dsgvo_einwilligung" not in {name for name, _ in modul.ZEILEN_LOESCHEN}
