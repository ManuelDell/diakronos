"""UX3g — Such-Endpunkt der Befehlspalette (`suche.global`).

Die Karte verlangt je Rolle die Rechte (Datenschutz-NEGATIV), die Grenzen und
das Praefix-Verhalten. Die Faelle hier sind genau diese Punkte:

  * Vertrag: nur {art, titel, ort, ziel} je Treffer, `art` aus `ARTEN`.
  * Anmeldung: Gast bekommt 403, nie Treffer.
  * Grenzen: < 2 Zeichen leer (kein Fehler), `limit` gedeckelt, `q`
    abgeschnitten, Ratenbegrenzung greift und ist abschaltbar.
  * Praefix: 2 Zeichen reichen fuer einen Treffer, 1 Zeichen nicht.
  * Rechte: Personen (B2-Sichtbarkeit, kein E-Mail-Glied), Gruppen
    (versteckt/intern), Termine (nur Kalender mit Leserecht), Lieder (nur
    aktive), Beitraege (nur veroeffentlichte), Einstellungen (nur Admin).
  * Negativ-Datenschutz: keine E-Mail/Telefonnummer in der Antwort, geloeschte
    Personen als „Geloeschte Person“, Papierkorb (docstatus=2) unsichtbar.
"""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from diakronos_app.api.suche import ARTEN
from diakronos_app.models.core import HasRole, Role, User, UserRole
from diakronos_app.models.diakonos import (
    Beitrag,
    Gruppe,
    Mitglied,
    WikiArtikel,
)
from diakronos_app.models.kronos import Element, Kalender, KalenderModerator
from diakronos_app.models.psalmos import Lied

PFAD = "diakronos.diakonos.api.suche.global"


# ── Hilfen ──────────────────────────────────────────────────────────────────


def _sitzung(patched_db):
    return patched_db()


def _rolle(db, user: str, rolle: str) -> None:
    if db.get(Role, rolle) is None:
        db.add(Role(name=rolle))
    db.add(HasRole(name=f"{user}|{rolle}", parent=user, parenttype="User",
                   parentfield="roles", role=rolle, idx=1))
    db.commit()


def _konto(db, user: str, *, mitglied: str | None = None, rolle: str | None = None,
           nachname: str = "Test", ancestor_path: str | None = "/Chor/Mitarbeiterkreis/") -> None:
    if db.get(User, user) is None:
        db.add(User(name=user, email=f"{user.lower()}@example.org",
                    full_name=user, enabled=True))
    if mitglied:
        db.add(Mitglied(name=mitglied, user=user, email=f"{user.lower()}@example.org",
                        vorname=user.capitalize(), nachname=nachname, status="Aktiv",
                        ancestor_path=ancestor_path))
    db.commit()
    if rolle:
        _rolle(db, user, rolle)


def _rufe(client, **kwargs):
    antwort = client.get(f"/api/method/{PFAD}", params=kwargs)
    return antwort


def _treffer(client, **kwargs) -> list[dict]:
    antwort = _rufe(client, **kwargs)
    assert antwort.status_code == 200, antwort.text
    return antwort.json()["message"]["treffer"]


def _titel(client, **kwargs) -> list[str]:
    return [t["titel"] for t in _treffer(client, **kwargs)]


@pytest.fixture()
def bestand(patched_db):
    """Kleiner, bewusst gemischter Bestand fuer alle Quellen."""
    db = patched_db()
    # Personen: sichtbar (ueberlappender Bereich) und fremd (anderer Bereich).
    db.add(Mitglied(name="M-001", user="anna", email="anna@example.org",
                    vorname="Miriam", nachname="Seifert", status="Aktiv",
                    telefonnummer="0170 123456", ancestor_path="/Chor/Mitarbeiterkreis/",
                    adressbuch_sichtbarkeit=json.dumps(
                        {"email": False, "telefonnummer": False})))
    db.add(Mitglied(name="M-002", user="bea", email="bea@example.org",
                    vorname="Mirjam", nachname="Fremd", status="Aktiv",
                    telefonnummer="0170 999999", ancestor_path="/Technik/Medienteam/"))
    db.add(Mitglied(name="M-003", email="weg@example.org",
                    vorname="Mirko", nachname="Ausgetreten", status="Ausgetreten",
                    austritt_datum=datetime(2026, 1, 1), ancestor_path="/Chor/Mitarbeiterkreis/"))
    # Papierkorb: docstatus=2 — darf nie auftauchen.
    db.add(Mitglied(name="M-004", email="mira@example.org", vorname="Mira",
                    nachname="Storniert", status="Aktiv", docstatus=2,
                    ancestor_path="/Chor/Mitarbeiterkreis/"))
    # Gruppen: oeffentlich, intern, versteckt, storniert.
    db.add(Gruppe(name="G-1", gruppenname="Mitarbeiterkreis", status="Aktiv",
                  sichtbarkeit="Öffentlich"))
    db.add(Gruppe(name="G-2", gruppenname="Mitarbeiter intern", status="Aktiv",
                  sichtbarkeit="Intern"))
    db.add(Gruppe(name="G-3", gruppenname="Mitarbeiter geheim", status="Aktiv",
                  sichtbarkeit="Versteckt"))
    db.add(Gruppe(name="G-4", gruppenname="Mitunterstützung", status="Aktiv",
                  sichtbarkeit="Öffentlich", docstatus=2))
    # Kalender mit Leserecht (Rolle „All“, KEIN Moderator) und einer mit
    # Moderatorrolle fuer „anna“; Termine in allen Status (UX3g2/F1).
    db.add(Kalender(name="K-1", calendar_name="Gemeindekalender"))
    db.add(Kalender(name="K-2", calendar_name="Leitungskalender"))
    db.add(Kalender(name="K-3", calendar_name="Moderationskalender"))
    db.add(UserRole(name="K-1|lesen", parent="K-1", parenttype="Kalender",
                    parentfield="leserechte", role="All", idx=1))
    db.add(UserRole(name="K-3|lesen", parent="K-3", parenttype="Kalender",
                    parentfield="leserechte", role="All", idx=1))
    db.add(KalenderModerator(name="KM-1", parent="K-3", parenttype="Kalender",
                             parentfield="kalendermoderatoren", user="anna", idx=1))
    db.add(Element(name="E-1", element_name="Mitarbeiterkreis-Abend",
                   element_calendar="K-1", status="Festgelegt",
                   element_start=datetime(2026, 11, 11, 19)))
    db.add(Element(name="E-2", element_name="Mitarbeitersitzung Leitung",
                   element_calendar="K-2", status="Festgelegt",
                   element_start=datetime(2026, 11, 12, 19)))
    db.add(Element(name="E-3", element_name="Mitarbeiter storniert",
                   element_calendar="K-1", docstatus=2, status="Festgelegt",
                   element_start=datetime(2026, 11, 13, 19)))
    # Status-Sonde: Vorschlag + abgelehnt im Kalender OHNE Moderatorrecht,
    # Freigabe + Vorschlag im Kalender MIT Moderatorrecht.
    db.add(Element(name="E-4", element_name="Mitarbeiter Vorschlag ohne Recht",
                   element_calendar="K-1", status="Vorschlag",
                   element_start=datetime(2026, 11, 14, 19)))
    db.add(Element(name="E-5", element_name="Mitarbeiter abgelehnt ohne Recht",
                   element_calendar="K-1", status="Abgelehnt",
                   element_start=datetime(2026, 11, 15, 19)))
    db.add(Element(name="E-6", element_name="Mitarbeiter freigegeben mit Recht",
                   element_calendar="K-3", status="Festgelegt",
                   element_start=datetime(2026, 11, 16, 19)))
    db.add(Element(name="E-7", element_name="Mitarbeiter Vorschlag mit Recht",
                   element_calendar="K-3", status="Vorschlag",
                   element_start=datetime(2026, 11, 17, 19)))
    db.add(Element(name="E-8", element_name="Mitarbeiter abgelehnt mit Recht",
                   element_calendar="K-3", status="Abgelehnt",
                   element_start=datetime(2026, 11, 18, 19)))
    # Lieder: aktiv und stillgelegt.
    db.add(Lied(name="L-1", titel="Mir nach, spricht Christus", aktiv=True))
    db.add(Lied(name="L-2", titel="Mirjam-Lied (stillgelegt)", aktiv=False))
    # Wiki + Beitraege: veroeffentlicht und nicht.
    db.add(WikiArtikel(name="W-1", titel="Mitarbeit im Wiki", kategorie="Organisation"))
    db.add(Beitrag(name="B-1", titel="Mitarbeiterfest 2026", kategorie="Gemeinde",
                   veroeffentlicht=True))
    db.add(Beitrag(name="B-2", titel="Mitarbeiter intern (Entwurf)",
                   kategorie="Gemeinde", veroeffentlicht=False))
    db.commit()
    from rechte_hilfe import uebernehmen
    uebernehmen(db)  # R-5: Altmodell-Rechte ins EINE Rechtesystem
    db.close()


@pytest.fixture()
def normale_client(client, bestand):
    """Angemeldet als Nicht-Admin mit eigenem Bereich „Chor/Mitarbeiterkreis“.

    Der Pfad traegt BEIDE Segmente in der Sichtbarkeitsregel (`_extract_segments`
    zerlegt ihn in eine Menge) — deshalb bekommt der fremde Bestand ein voellig
    anderes Segmentpaar, sonst waere er ueber „Chor“ mit sichtbar.
    """
    from diakronos_app.frappe_compat import set_user
    import diakronos_app.db as dbmod

    db = dbmod.SessionLocal()
    # M-001 gehoert bereits „anna“ (bestand) — hier nur das Konto anlegen.
    _konto(db, "anna")
    # Eigenes Mitglied M-001 an den Kontonamen binden: `_get_current_user_mitglied`
    # vergleicht normalisierte Adressen (User.email ↔ Mitglied.email), nicht
    # den Benutzernamen.
    eigenes = db.get(Mitglied, "M-001")
    eigenes.user = "anna"
    db.commit()
    db.close()
    set_user("anna")
    yield client


@pytest.fixture()
def admin_client(client, bestand):
    """Angemeldet als Administrator (Client-Fixture setzt die Identitaet)."""
    return client


# ── Vertrag und Anmeldung ───────────────────────────────────────────────────


def test_gast_bekommt_403_und_keine_treffer(guest_client, bestand):
    antwort = _rufe(guest_client, q="Miriam")
    assert antwort.status_code in (401, 403), antwort.text
    assert "treffer" not in antwort.text


def test_antwort_hat_genau_die_vertragsform(admin_client):
    antwort = _rufe(admin_client, q="Mitarbeiter", limit=20)
    assert antwort.status_code == 200, antwort.text
    rumpf = antwort.json()["message"]
    assert set(rumpf) == {"q", "treffer", "quellen"}
    assert rumpf["q"] == "Mitarbeiter"
    assert set(rumpf["quellen"]) == set(ARTEN)
    assert rumpf["treffer"], "der Bestand muss Treffer liefern"
    for treffer in rumpf["treffer"]:
        assert set(treffer) == {"art", "titel", "ort", "ziel"}
        assert treffer["art"] in ARTEN
        assert treffer["titel"] and treffer["ziel"].startswith("#/")
        assert treffer["ort"], "jeder Treffer traegt seinen Ort (Prinzip N7)"


def test_trefferreihenfolge_folgt_den_arten(admin_client):
    treffer = _treffer(admin_client, q="Mitarbeiter", limit=20)
    rang = [ARTEN.index(t["art"]) for t in treffer]
    assert rang == sorted(rang), "Gruppierung der Palette setzt die Reihenfolge voraus"


# ── Grenzen ─────────────────────────────────────────────────────────────────


def test_unter_zwei_zeichen_leer_ohne_fehler(admin_client):
    for begriff in ("", " ", "M", "  M  "):
        antwort = _rufe(admin_client, q=begriff)
        assert antwort.status_code == 200, antwort.text
        assert antwort.json()["message"]["treffer"] == []


def test_praefix_ab_zwei_zeichen(admin_client):
    # „Mi“ ist ein Praefix von „Mitarbeiterkreis“/„Miriam“ — zwei Zeichen
    # genuegen, ein Zeichen nicht (Grenze oben).
    assert _titel(admin_client, q="Mi"), "zwei Zeichen muessen treffen"
    assert _titel(admin_client, q="M") == []


def test_limit_gilt_je_quelle_und_ist_gedeckelt(admin_client):
    # Drei Wiki-/Beitrags-/Gruppentreffer „Mitarbeiter…“ sind vorhanden; mit
    # limit=1 darf JE Quelle genau einer kommen.
    treffer = _treffer(admin_client, q="Mitarbeiter", limit=1)
    je_art: dict[str, int] = {}
    for t in treffer:
        je_art[t["art"]] = je_art.get(t["art"], 0) + 1
    assert all(anzahl == 1 for anzahl in je_art.values()), je_art
    assert len({t["art"] for t in treffer}) > 1, "mehrere Quellen muessen liefern"

    # limit=999 wird auf MAX_LIMIT gedeckelt, nicht abgelehnt.
    antwort = _rufe(admin_client, q="Mitarbeiter", limit=999)
    assert antwort.status_code == 200
    assert len(_treffer(admin_client, q="Mitarbeiter", limit=999)) <= 7 * 20


def test_langer_begriff_wird_abgeschnitten(admin_client):
    antwort = _rufe(admin_client, q="Mitarbeiter" * 40)
    assert antwort.status_code == 200
    assert len(antwort.json()["message"]["q"]) <= 100


def test_ratenbegrenzung_greift_und_ist_abschaltbar(admin_client, monkeypatch, fake_redis):
    from diakronos_app import suche_bremse
    from diakronos_app.settings import settings

    # Ein frischer Zaehler: der Client-Fixture hat fuer andere Tests bereits
    # mitgezaehlt, deshalb eigener Praefix je Testlauf.
    bremse = suche_bremse.Bremse(client_factory=lambda: fake_redis)
    monkeypatch.setattr(suche_bremse.bremse, "pruefe", bremse.pruefe)
    monkeypatch.setattr(suche_bremse.bremse, "zaehler_stand", bremse.zaehler_stand)
    monkeypatch.setattr(settings, "suche_max", 2)
    monkeypatch.setattr(settings, "suche_fenster_sekunden", 60)
    fake_redis.delete(bremse.schluessel("Administrator"))

    assert _rufe(admin_client, q="Miriam").status_code == 200
    assert _rufe(admin_client, q="Miriam").status_code == 200
    gebremst = _rufe(admin_client, q="Miriam")
    assert gebremst.status_code == 429, gebremst.text
    # Auch der GEBREMSTE Versuch wird gezaehlt (INCR vor der Pruefung) — sonst
    # koennte ein Skript die Grenze durch Weiterklopfen nicht verschieben und
    # das Fenster waere nicht mehr ablesbar.
    assert bremse.zaehler_stand("Administrator") == 3

    # `SUCHE_MAX = 0` = ausdruecklich aus.
    monkeypatch.setattr(settings, "suche_max", 0)
    assert _rufe(admin_client, q="Miriam").status_code == 200


def test_bremse_faellt_bei_redis_aus_fail_closed(admin_client, monkeypatch):
    from redis.exceptions import RedisError

    from diakronos_app import suche_bremse
    from diakronos_app.settings import settings

    class Kaputt:
        def pipeline(self, transaction=True):  # noqa: ARG002
            raise RedisError("weg")

    monkeypatch.setattr(settings, "suche_max", 5)
    monkeypatch.setattr(suche_bremse.bremse, "_client_factory", lambda: Kaputt())
    assert _rufe(admin_client, q="Miriam").status_code == 429


# ── Rechte: Personen ────────────────────────────────────────────────────────


def test_personen_nur_im_eigenen_bereich(normale_client):
    """R-9/R-11b (Manuel 11.11.): Namen ALLER Mitglieder sieht jedes
    Gemeindemitglied — auch aus einem fremden Bereich (vorher ancestor_path)."""
    titel = _titel(normale_client, q="Mir")
    assert "Miriam Seifert" in titel
    assert "Mirjam Fremd" in titel


def test_personen_kein_email_seitenkanal(normale_client):
    # Suche nach der Adresse einer fremden Person liefert nichts — das
    # E-Mail-Glied ist fuer Nicht-Admins grundsaetzlich gestrichen (B2).
    assert _titel(normale_client, q="bea@example.org") == []
    assert _titel(normale_client, q="bea") == []


def test_keine_kontaktdaten_in_der_antwort(normale_client):
    antwort = _rufe(normale_client, q="Mir")
    roh = antwort.text
    assert "0170" not in roh, "keine Telefonnummer in Treffern"
    assert "@example.org" not in roh, "keine E-Mail-Adresse in Treffern"


def test_ausgetretene_person_wird_gekennzeichnet(normale_client):
    treffer = [t for t in _treffer(normale_client, q="Mirko")]
    assert treffer, "ausgetretene Personen bleiben auffindbar"
    assert "Ausgetreten" in treffer[0]["ort"]
    # UX3g2 (F2): der Klarname einer ausgetretenen Person steht NICHT in der
    # Palette — dieselbe Kurzform wie Adressbuch/Mitgliederliste (ID-1).
    titel = _titel(normale_client, q="Mirko")
    assert "Mirko A." in titel, titel
    assert "Mirko Ausgetreten" not in titel, titel
    assert all("Ausgetreten" not in t for t in titel), titel


def test_geloeschte_person_ohne_namen(normale_client, patched_db):
    db = patched_db()
    db.add(Mitglied(name="geloescht-4f2a", email="anonym@example.org", vorname="Miriam",
                    nachname="Geloescht", status="geloescht",
                    ancestor_path="/Chor/Mitarbeiterkreis/"))
    db.commit()
    db.close()

    treffer = [t for t in _treffer(normale_client, q="Miriam")]
    assert treffer, "die Zeile verschwindet nicht still"
    assert all(t["titel"] != "Miriam Geloescht" for t in treffer)
    assert any("Gelöschte Person" in t["titel"] for t in treffer)


def test_papierkorb_ist_ausgeschlossen(admin_client):
    titel = _titel(admin_client, q="Mira")
    assert "Mira Storniert" not in titel
    assert "Mitunterstützung" not in _titel(admin_client, q="Mitunterstützung")


# ── Rechte: Gruppen ─────────────────────────────────────────────────────────


def test_gruppen_versteckt_und_intern(normale_client):
    titel = _titel(normale_client, q="Mitarbeiter")
    assert "Mitarbeiterkreis" in titel, "oeffentliche Gruppe ist sichtbar"
    assert "Mitarbeiter geheim" not in titel, "versteckte Gruppe nie"
    assert "Mitarbeiter intern" not in titel, "fremde interne Gruppe nie"
    assert "Mitunterstützung" not in titel, "stornierte Gruppe nie"


def test_eigene_interne_gruppe_ist_sichtbar(normale_client, patched_db):
    from diakronos_app.models.diakonos import Gruppenmitgliedschaft

    db = patched_db()
    db.add(Gruppenmitgliedschaft(name="GM-1", parent="G-2", parenttype="Gruppe",
                                 parentfield="mitglieder", mitglied="M-001",
                                 status="Aktiv", idx=1))
    db.commit()
    db.close()

    assert "Mitarbeiter intern" in _titel(normale_client, q="Mitarbeiter")


def test_eigene_versteckte_gruppe_ist_findbar(normale_client, patched_db):
    """UX3g2 (F4): „Versteckt“ = nicht im Verzeichnis, nicht unsichtbar.

    Die Gruppenansicht zeigt die eigenen Gruppen immer („Meine Gruppen“);
    die Palette folgt ihr — fremde versteckte Gruppen bleiben verborgen.
    """
    from diakronos_app.models.diakonos import Gruppenmitgliedschaft

    titel_vorher = _titel(normale_client, q="Mitarbeiter")
    assert "Mitarbeiter geheim" not in titel_vorher

    db = patched_db()
    db.add(Gruppenmitgliedschaft(name="GM-2", parent="G-3", parenttype="Gruppe",
                                 parentfield="mitglieder", mitglied="M-001",
                                 status="Aktiv", idx=1))
    db.commit()
    db.close()

    titel = _titel(normale_client, q="Mitarbeiter")
    assert "Mitarbeiter geheim" in titel, titel
    # … und die FREMDEN versteckten Gruppen bleiben draussen.
    db = patched_db()
    db.add(Gruppe(name="G-5", gruppenname="Mitarbeiter fremdgeheim", status="Aktiv",
                  sichtbarkeit="Versteckt"))
    db.commit()
    db.close()
    titel = _titel(normale_client, q="Mitarbeiter")
    assert "Mitarbeiter geheim" in titel
    assert "Mitarbeiter fremdgeheim" not in titel, titel


def test_admin_sieht_interne_gruppe(admin_client):
    assert "Mitarbeiter intern" in _titel(admin_client, q="Mitarbeiter")


# ── Rechte: Termine ─────────────────────────────────────────────────────────


def test_termine_nur_aus_kalendern_mit_leserecht(normale_client):
    titel = _titel(normale_client, q="Mitarbeiter")
    assert "Mitarbeiterkreis-Abend" in titel
    assert "Mitarbeitersitzung Leitung" not in titel, "Kalender ohne Leserecht"


def test_stornierter_termin_ist_ausgeschlossen(admin_client):
    assert "Mitarbeiter storniert" not in _titel(admin_client, q="Mitarbeiter")


# UX3g2 (F1): Statusregel wie `calendar_get` — Nicht-Moderatoren sehen nur
# „Festgelegt“, Moderatoren alles AUSSER „Abgelehnt“.


def test_vorschlag_und_abgelehnt_nur_fuer_moderatoren(normale_client):
    titel = _titel(normale_client, q="Mitarbeiter")
    # Kalender mit Leserecht, ohne Moderatorrecht: nur die Freigabe.
    assert "Mitarbeiterkreis-Abend" in titel
    assert "Mitarbeiter Vorschlag ohne Recht" not in titel, titel
    assert "Mitarbeiter abgelehnt ohne Recht" not in titel, titel
    # Kalender mit Moderatorrecht: Freigabe UND Vorschlag, nie „Abgelehnt“.
    assert "Mitarbeiter freigegeben mit Recht" in titel, titel
    assert "Mitarbeiter Vorschlag mit Recht" in titel, titel
    assert "Mitarbeiter abgelehnt mit Recht" not in titel, titel


def test_moderator_sieht_vorschlag_aber_nie_abgelehnt(admin_client):
    titel = _titel(admin_client, q="Mitarbeiter")
    assert "Mitarbeiter Vorschlag ohne Recht" in titel, titel
    assert "Mitarbeiter Vorschlag mit Recht" in titel, titel
    assert "Mitarbeiter abgelehnt ohne Recht" not in titel, titel
    assert "Mitarbeiter abgelehnt mit Recht" not in titel, titel


def test_termin_ziel_fuehrt_zum_kalender(admin_client):
    treffer = [t for t in _treffer(admin_client, q="Mitarbeiterkreis-Abend")]
    assert treffer
    assert treffer[0]["ziel"].startswith("#/kalender")
    assert "Gemeindekalender" in treffer[0]["ort"]


# ── Rechte: Lieder, Wiki, Beitraege, Einstellungen ──────────────────────────


def test_nur_aktive_lieder(normale_client):
    titel = _titel(normale_client, q="Mir")
    assert "Mir nach, spricht Christus" in titel
    assert "Mirjam-Lied (stillgelegt)" not in titel


def test_wiki_und_veroeffentlichte_beitraege(normale_client):
    assert "Mitarbeit im Wiki" in _titel(normale_client, q="Mitarbeit")
    titel = _titel(normale_client, q="Mitarbeiter")
    assert "Mitarbeiterfest 2026" in titel
    assert "Mitarbeiter intern (Entwurf)" not in titel


def test_einstellungen_nur_fuer_admins(client, bestand):
    # Beide Laeufe auf DEMSELBEN Client: `normale_client` und `client` sind
    # dieselbe Instanz (geteilte Fixtures), ein zweiter Fixture-Aufruf wuerde
    # den Benutzer wieder auf „anna“ setzen.
    from diakronos_app.frappe_compat import reset_user, set_user

    set_user("anna")
    assert all(t["art"] != "einstellung" for t in _treffer(client, q="Gemeinde"))

    reset_user()
    set_user("Administrator")
    treffer_admin = [t for t in _treffer(client, q="Gemeinde")
                     if t["art"] == "einstellung"]
    assert treffer_admin, "Admins bekommen Stichworte der Einstellungen"
    assert treffer_admin[0]["ziel"].startswith("#/einstellungen/")


# ── Platzhalter der Eingabe (F3) ────────────────────────────────────────────


def test_like_platzhalter_werden_entschaerft(admin_client):
    """UX3g2 (F3): `%` und `_` in `q` sind Text, keine Joker.

    Ohne Entschaerfung waere `q="__"` ein Zwei-Zeichen-Joker und traefe
    jeden Datensatz mit zwei Zeichen; `q="%%"` traefe alles. Beides darf
    NICHTS liefern — kein Bestand traegt diese Zeichen.
    """
    for begriff in ("%%", "__", "\\", "%a%", "_i_"):
        antwort = _rufe(admin_client, q=begriff)
        assert antwort.status_code == 200, antwort.text
        rumpf = antwort.json()["message"]
        assert rumpf["treffer"] == [], (begriff, rumpf["treffer"])
        assert all(anzahl == 0 for anzahl in rumpf["quellen"].values()), rumpf["quellen"]

    # Gegenprobe: das Zeichen selbst ist suchbar (kein Filter-Fehler).
    titel = _titel(admin_client, q="Mir")
    assert titel, "die normale Suche bleibt unberuehrt"


# ── Rolle Gast (F5) ─────────────────────────────────────────────────────────


def test_gast_rolle_bekommt_403_und_keine_treffer(guest_client, bestand, patched_db):
    """UX3g2 (F5): Die Rolle Gast — Endpunkt und Alias antworten gleich."""
    from diakronos_app.frappe_compat import set_user

    # Auch mit gesetzter Identitaet „Guest“ (Naht wie in der Sitzung) — nicht
    # nur ohne Sitzungscookie — gibt es keine Treffer.
    set_user("Guest")
    try:
        for pfad in (PFAD, "diakronos.diakonos.api.suche.global_"):
            for begriff in ("Mir", "Mitarbeiter", "%%"):
                antwort = guest_client.get(f"/api/method/{pfad}", params={"q": begriff})
                assert antwort.status_code in (401, 403), (pfad, antwort.status_code)
                assert "treffer" not in antwort.text, antwort.text
    finally:
        from diakronos_app.frappe_compat import reset_user

        reset_user()

