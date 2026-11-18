"""CHAT-R2b — Personensuche für „Nachrichten“ (Backend, ``chat.personen_suchen``).

Konzept ``docs/konzepte/CHAT-KONZEPT.md`` 10.1 Punkt 2–4 und 10.4; Karte
CHAT-R2b-API. Entscheidung Manuel 17.11.2026: **alle aktiven
Gemeindemitglieder sind für jedes Gemeindemitglied auffindbar**; Personen ohne
Konto sind auffindbar, tragen aber ``hat_konto: false``.

Geprüft wird gegen den ECHTEN Endpunkt (``api/chat.py``) und den ECHTEN
Rechte-Kern (``rechte/kern.py``) — keine Attrappe:

  * ``Guest`` bekommt keinen Treffer, auch nicht über HTTP
  * ein ausgetretenes Mitglied erscheint NIE
  * ein nicht freigegebenes Feld kommt im Treffer NICHT VOR (Schlüssel fehlt)
  * Person ohne Konto → ``hat_konto: false`` UND ``darf_schreiben: false``
  * sich selbst finden ist erlaubt, ``darf_schreiben`` bleibt ``false``
  * ein Nicht-Gemeindemitglied als Aufrufer bekommt eine leere Liste
  * Grenze 20 / max 50, sortiert nach Nachname, Vorname
  * Suchbegriff ab 2 Zeichen, Umlaute egal („muller“ findet „Müller“)

Aufruf (Karte):
    docker run --rm --network none --entrypoint python -v <wt>:/repo:ro \\
      -w /repo/backend -e PYTHONPATH=/repo/backend/src:/repo/backend/tests:/repo/tools \\
      -e PYTHONDONTWRITEBYTECODE=1 <vorbau> -m pytest -q -p no:cacheprovider \\
      tests/test_chat_r2b_suche.py
"""

from __future__ import annotations

import importlib
import json

import pytest
from fastapi.testclient import TestClient

#: Die Test-Naht liegt im MODUL ``frappe_compat.session`` — ``from
#: diakronos_app.frappe_compat import session`` liefert dagegen das
#: Sitzungs-OBJEKT (das Paket bindet den Namen um, s. ``conftest.py``).
_session_mod = importlib.import_module("diakronos_app.frappe_compat.session")

from diakronos_app.models.core import HasRole, User
from diakronos_app.models.diakonos import (
    Gruppe,
    Gruppenmitgliedschaft,
    Mitglied,
)

ANNA = "anna@x.org"      # Aufruferin, mit Konto
BERT = "bert@x.org"      # mit Konto, fremde Person
OHNE = "ohne@x.org"      # Konto, aber Mitgliedsdatensatz OHNE Konto-Verknuepfung
CLARA = "clara@x.org"    # Konto, aber AUSGETRETEN
DUMP = "dump@x.org"      # Konto ohne Mitgliedsdatensatz (kein Gemeindemitglied)
AUSG = "ausg@x.org"      # Konto eines ausgeschlossenen Mitglieds (Aufrufer)


def _set_user(konto: str) -> None:
    _session_mod.set_user(konto)


@pytest.fixture()
def welt(patched_db):
    """Vier Mitglieder + Konten: eine Aufruferin, ein Kollege, einer ohne
    Konto-Verknüpfung, eine Ausgetretene — und zwei Konten ohne Mitglied."""
    s = patched_db()
    for konto, kurz in [(ANNA, "Anna"), (BERT, "Bert"), (OHNE, "Ohne"),
                        (CLARA, "Clara"), (DUMP, "Dump"), (AUSG, "Ausg")]:
        s.add(User(name=konto, email=konto, enabled=1, full_name=kurz))
    s.add_all([
        Mitglied(name="M-Anna", vorname="Anna", nachname="Beispiel",
                 email=ANNA, user=ANNA, status="Aktiv"),
        Mitglied(name="M-Bert", vorname="Bert", nachname="Brandner",
                 email=BERT, user=BERT, status="Aktiv"),
        # Ohne Konto: ``user`` bleibt leer — auffindbar, aber nicht beschreibbar.
        Mitglied(name="M-Ohne", vorname="Olaf", nachname="Ohnberg",
                 email=OHNE, user=None, status="Aktiv"),
        # Ausgetreten: nie in der Suche.
        Mitglied(name="M-Clara", vorname="Clara", nachname="Clausen",
                 email=CLARA, user=CLARA, status="Ausgetreten"),
        # Ausgeschlossen: nie auffindbar (und als Aufrufer ohne Recht).
        Mitglied(name="M-Ausg", vorname="Achim", nachname="Ausgeschlossen",
                 email=AUSG, user=AUSG, status="Aktiv", ausgeschlossen=True),
        # Geloeschte Person: neutraler Name, kein Treffer.
        Mitglied(name="geloescht-abc123", vorname="Gela", nachname="Geloescht",
                 email=None, status="geloescht"),
    ])
    s.commit()
    yield s
    s.close()


def _suche(**kwargs) -> dict:
    from diakronos_app.api import chat as C

    return C.personen_suchen(**kwargs)


def _kennungen(antwort: dict) -> list[str]:
    return [t["mitglied"] for t in antwort["treffer"]]


def _treffer(antwort: dict, mitglied: str) -> dict:
    for t in antwort["treffer"]:
        if t["mitglied"] == mitglied:
            return t
    raise AssertionError(f"{mitglied} fehlt in {_kennungen(antwort)}")


def _sichtbarkeit(s, mitglied: str, **schalter) -> None:
    """Schreibt den Sichtbarkeits-Blob direkt (der Umweg über die API
    braucht eine eigene Sitzung und würde den Test von der DB entkoppeln)."""
    blob = {
        "email": schalter.get("email", False),
        "telefonnummer": schalter.get("telefonnummer", False),
        "adresse": schalter.get("adresse", False),
        "geburtstag": schalter.get("geburtstag", False),
    }
    m = s.get(Mitglied, mitglied)
    m.adressbuch_sichtbarkeit = json.dumps(blob)
    s.commit()


# ════════════════════════════════════════════════════════════════════════════
# 1) Grundfall: aktive Personen sind auffindbar
# ════════════════════════════════════════════════════════════════════════════


def test_aktive_personen_sind_auffindbar(welt):
    """Ein Gemeindemitglied findet die anderen aktiven Gemeindemitglieder."""
    _set_user(ANNA)
    antwort = _suche(q="bert")
    assert _kennungen(antwort) == ["M-Bert"]
    t = antwort["treffer"][0]
    assert t["anzeigename"] == "Bert Brandner"
    assert t["hat_konto"] is True
    assert t["darf_schreiben"] is True
    assert "bild" in t


def test_die_antwort_ist_eine_liste_mit_grenze(welt):
    """Form: ``{treffer: [...], limit: 20}`` — die SPA liest beides."""
    _set_user(ANNA)
    antwort = _suche(q="e")
    assert antwort == {"treffer": [], "limit": 20}  # 1 Zeichen reicht nicht

    antwort = _suche(q="be")
    assert antwort["limit"] == 20
    assert isinstance(antwort["treffer"], list)


@pytest.mark.parametrize("q", ["", None, " ", "a", "  b  "[:1]])
def test_zu_kurzer_oder_leerer_begriff_ist_leer(welt, q):
    """Unter 2 Zeichen gibt es keine Suche — nicht einmal ein Teilergebnis."""
    _set_user(ANNA)
    assert _suche(q=q)["treffer"] == []


def test_suche_trifft_vor_und_nachname_und_die_phrase(welt):
    """Name als Suchbegriff: Vor-, Nachname, Teilstring, „Anna Bei…“."""
    _set_user(ANNA)
    for begriff in ("bert", "BRAND", "randn", "bert bran", "brandner bert"):
        assert "M-Bert" in _kennungen(_suche(q=begriff)), begriff


def test_umlaute_und_schreibweise_egal(welt):
    """„weiss“ findet „Weiß“, „mueller“ findet „Müller“ — dieselbe Faltung
    wie in der Mitgliederliste (``_suche_normalisieren``: ü → ue). Die
    Schreibweise „muller“ findet „Müller“ bewusst NICHT: die Faltung macht aus
    „Müller“ die Form „mueller“, und ein nicht aufgelöster Umlaut ist eine
    ANDERE Zeichenkette — dieselbe Entscheidung wie in der Liste."""
    s = welt
    # Eigene Konten: zwei Mitglieder mit demselben `user` machten die
    # Login→Mitglied-Zuordnung mehrdeutig — und der Rechte-Kern antwortet
    # darauf fail closed („kein Gemeindemitglied“). Genau so soll es sein.
    for konto in ("jm@x.org", "sw@x.org"):
        s.add(User(name=konto, email=konto, enabled=1, full_name=konto))
    s.add(Mitglied(name="M-Mueller", vorname="Jürgen", nachname="Müller",
                   email="mueller@x.org", user="jm@x.org", status="Aktiv"))
    s.add(Mitglied(name="M-Weiss", vorname="Sabine", nachname="Weiß",
                   email="weiss@x.org", user="sw@x.org", status="Aktiv"))
    s.commit()
    _set_user(ANNA)
    assert "M-Mueller" in _kennungen(_suche(q="mueller"))
    assert "M-Mueller" in _kennungen(_suche(q="MÜLLER"))
    assert "M-Mueller" in _kennungen(_suche(q="juergen"))
    assert "M-Weiss" in _kennungen(_suche(q="weiss"))


# ════════════════════════════════════════════════════════════════════════════
# 2) Fail closed: Guest, fremde Konten, Ausgetretene
# ════════════════════════════════════════════════════════════════════════════


def test_gast_bekommt_keinen_treffer(welt):
    """Kein Login → leere Liste (kein ``403``: der Gast soll nicht einmal
    erfahren, dass es einen Suchendpunkt mit Inhalt gibt)."""
    _session_mod.reset_user()
    assert _suche(q="bert")["treffer"] == []


def test_gast_bekommt_auch_ueber_http_keinen_treffer(welt, guest_client):
    """10.4, erster Punkt: ``Guest`` bekommt auch bei direkter Adresse nichts."""
    r = guest_client.get("/api/method/chat.personen_suchen", params={"q": "bert"})
    assert r.status_code in (200, 403, 401), r.text
    if r.status_code == 200:
        inhalt = r.json().get("message") or {}
        assert inhalt.get("treffer") == []


def test_ausgetretenes_mitglied_erscheint_nie(welt):
    """10.4, zweiter Punkt: auch wenn das Profil noch erreichbar ist."""
    _set_user(ANNA)
    assert _suche(q="clara")["treffer"] == []
    assert _suche(q="clausen")["treffer"] == []
    # Gegenprobe: der Vorfilter sieht die Zeile sehr wohl (Namen sind da) —
    # die Entscheidung faellt im Rechte-Kern, nicht in der Abfrage.
    assert "M-Clara" not in _kennungen(_suche(q="cla"))


def test_ausgeschlossenes_mitglied_erscheint_nie(welt):
    _set_user(ANNA)
    assert _suche(q="achim")["treffer"] == []
    assert _suche(q="ausgeschlossen")["treffer"] == []


def test_geloeschte_person_erscheint_nie(welt):
    _set_user(ANNA)
    assert _suche(q="gela")["treffer"] == []
    assert _suche(q="geloescht")["treffer"] == []


def test_nicht_gemeindemitglied_als_aufrufer_bekommt_leere_liste(welt):
    """Ein Konto ohne Mitgliedsdatensatz ist kein Gemeindemitglied — fail closed."""
    _set_user(DUMP)
    assert _suche(q="bert")["treffer"] == []
    assert _suche(q="be")["treffer"] == []


def test_ausgeschlossener_aufrufer_bekommt_leere_liste(welt):
    """Ein ausgeschlossenes Mitglied sucht niemanden (Kern: ``ist_gemeindemitglied``)."""
    _set_user(AUSG)
    assert _suche(q="bert")["treffer"] == []


def test_fehler_wird_zu_leerer_liste(welt, monkeypatch):
    """Fail closed heisst auch: ein kaputter Rechte-Kern liefert KEINE Treffer
    — nicht eine rohe Ausnahme und keine ungeprüfte Liste."""
    from diakronos_app.api import chat as C

    def kaputt(benutzer, ziel):  # noqa: ARG001
        raise RuntimeError("Rechte-Kern nicht erreichbar")

    monkeypatch.setattr("diakronos_app.rechte.darf_person_finden", kaputt)
    _set_user(ANNA)
    assert C.personen_suchen(q="bert")["treffer"] == []


# ════════════════════════════════════════════════════════════════════════════
# 3) Personen ohne Konto und die eigene Person
# ════════════════════════════════════════════════════════════════════════════


def test_person_ohne_konto_ist_auffindbar_aber_nicht_beschreibbar(welt):
    """10.1 Punkt 3: ausgegraut statt versteckt — ``hat_konto``/``darf_schreiben``."""
    _set_user(ANNA)
    t = _treffer(_suche(q="olaf"), "M-Ohne")
    assert t["hat_konto"] is False
    assert t["darf_schreiben"] is False
    assert t["anzeigename"] == "Olaf Ohnberg"


def test_sich_selbst_finden_ist_erlaubt_aber_nicht_beschreibbar(welt):
    """Man findet sich selbst; schreiben an sich selbst ist gesperrt (Kern: ``selbst``)."""
    _set_user(ANNA)
    t = _treffer(_suche(q="anna bei"), "M-Anna")
    assert t["hat_konto"] is True
    assert t["darf_schreiben"] is False


# ════════════════════════════════════════════════════════════════════════════
# 4) Feldauswahl: kein neuer Weg an der Maskierung vorbei
# ════════════════════════════════════════════════════════════════════════════


def _pii_setzen(s, mitglied: str) -> None:
    m = s.get(Mitglied, mitglied)
    m.telefonnummer = "0170-2220002"
    m.postleitzahl = "73728"
    m.wohnort = "Esslingen"
    m.straße = "Nebenweg"
    m.nummer = "2"
    m.notiz = "VERTRAULICHE-NOTIZ"
    m.datenschutz_einwilligung = True
    s.commit()


def test_nicht_freigegebenes_feld_fehlt_ganz(welt):
    """10.4, dritter Punkt: der Schlüssel ist NICHT da — nicht ``null``."""
    _pii_setzen(welt, "M-Bert")
    _sichtbarkeit(welt, "M-Bert")  # alles aus
    _set_user(ANNA)
    t = _treffer(_suche(q="bert"), "M-Bert")
    for feld in ("email", "telefonnummer", "postleitzahl", "wohnort",
                 "straße", "nummer", "geburtstag", "notiz",
                 "adressbuch_sichtbarkeit", "datenschutz_einwilligung",
                 "status", "user", "vorname", "nachname"):
        assert feld not in t, f"{feld} darf im Treffer nicht stehen: {t}"
    # Die Pflichtfelder sind trotzdem da.
    assert set(t) == {"mitglied", "anzeigename", "bild", "hat_konto",
                      "darf_schreiben"}


def test_freigegebenes_feld_kommt_mit_wert(welt):
    """Freigabe wirkt einzeln: nur ``email`` frei → nur ``email`` im Treffer."""
    _pii_setzen(welt, "M-Bert")
    _sichtbarkeit(welt, "M-Bert", email=True)
    _set_user(ANNA)
    t = _treffer(_suche(q="bert"), "M-Bert")
    assert t["email"] == BERT
    assert "telefonnummer" not in t
    assert "wohnort" not in t


def test_adressfreigabe_gibt_genau_die_adressfelder(welt):
    """Der Schalter ``adresse`` deckt PLZ/Ort/Straße/Nummer — nicht mehr."""
    _pii_setzen(welt, "M-Bert")
    _sichtbarkeit(welt, "M-Bert", adresse=True)
    _set_user(ANNA)
    t = _treffer(_suche(q="bert"), "M-Bert")
    assert (t.get("postleitzahl"), t.get("wohnort")) == ("73728", "Esslingen")
    assert t.get("straße") == "Nebenweg" and t.get("nummer") == "2"
    assert "email" not in t and "telefonnummer" not in t
    assert "notiz" not in t


def test_treffer_hat_weniger_felder_als_das_profil(welt):
    """10.4: „die Suche liefert weniger Felder als das Profil“ — auch bei
    vollständiger Freigabe (kein Verwaltungsfeld, keine Einwilligung)."""
    _pii_setzen(welt, "M-Bert")
    _sichtbarkeit(welt, "M-Bert", email=True, telefonnummer=True,
                  adresse=True, geburtstag=True)
    _set_user(ANNA)
    t = _treffer(_suche(q="bert"), "M-Bert")
    assert "notiz" not in t and "datenschutz_einwilligung" not in t
    assert "adressbuch_sichtbarkeit" not in t
    assert "owner" not in t and "modified_by" not in t


# ════════════════════════════════════════════════════════════════════════════
# 5) Grenze und Reihenfolge
# ════════════════════════════════════════════════════════════════════════════


def _viele(s, anzahl: int) -> None:
    for i in range(anzahl):
        konto = f"v{i}@x.org"
        s.add(User(name=konto, email=konto, enabled=1, full_name=f"V{i}"))
        s.add(Mitglied(name=f"M-V{i:03d}", vorname=f"Vorname{i:02d}",
                       nachname=f"Zander{i:02d}", email=konto, user=konto,
                       status="Aktiv"))
    s.commit()


def test_standardgrenze_ist_20(welt):
    _viele(welt, 30)
    _set_user(ANNA)
    antwort = _suche(q="zander")
    assert antwort["limit"] == 20
    assert len(antwort["treffer"]) == 20


def test_grenze_max_50(welt):
    _viele(welt, 60)
    _set_user(ANNA)
    antwort = _suche(q="zander", limit=1000)
    assert antwort["limit"] == 50
    assert len(antwort["treffer"]) == 50


def test_kleineres_limit_wird_beachtet(welt):
    _viele(welt, 10)
    _set_user(ANNA)
    antwort = _suche(q="zander", limit=3)
    assert antwort["limit"] == 3
    assert len(antwort["treffer"]) == 3


def test_unsinniges_limit_faellt_auf_die_vorgabe(welt):
    _set_user(ANNA)
    assert _suche(q="bert", limit="viele")["limit"] == 20
    assert _suche(q="bert", limit=0)["limit"] == 1


def test_sortiert_nach_nachname_dann_vorname(welt):
    """Karte Punkt 3: sortiert nach Nachname, Vorname."""
    s = welt
    for konto, vor, nach in [("s1@x.org", "Zoe", "Albers"),
                             ("s2@x.org", "Anton", "Albers"),
                             ("s3@x.org", "Bea", "Albers")]:
        s.add(User(name=konto, email=konto, enabled=1, full_name=konto))
        s.add(Mitglied(name=f"M-{konto}", vorname=vor, nachname=nach,
                       email=konto, user=konto, status="Aktiv"))
    s.commit()
    _set_user(ANNA)
    namen = [t["anzeigename"] for t in _suche(q="albers")["treffer"]]
    assert namen == ["Anton Albers", "Bea Albers", "Zoe Albers"]


# ════════════════════════════════════════════════════════════════════════════
# 6) Registrierung, Methoden und Bild
# ════════════════════════════════════════════════════════════════════════════


def test_endpunkt_ist_registriert_und_lesend():
    """SEC-11: lesender Endpunkt, GET erlaubt, kein Gast — und im Inventar
    als ``lesend`` geführt (Name ``personen_suchen`` deutet nicht auf Schreiben)."""
    from diakronos_app.api import chat as C
    from diakronos_app.frappe_compat import registry

    assert registry.lookup("chat.personen_suchen") is C.personen_suchen
    optionen = registry.options_for(C.personen_suchen)
    assert optionen.get("allow_guest") is False
    assert optionen.get("methods") in (None, ("GET",), ("GET", "POST"))

    from pathlib import Path

    # Das Inventar liegt IM Python-Paket (Regel 13). Gesucht wird vom
    # Testverzeichnis aus nach oben — Repo-Lauf (`<repo>/backend/tests`) und
    # Image-Lauf (`/app/tests`) sind beide abgedeckt; kein Raten ueber `tools/`.
    hier = Path(__file__).resolve().parent
    inventar = next(
        (b / "src" / "diakronos_app" / "frappe_compat" / "inventar" / "whitelist.json"
         for b in (hier.parent, hier.parent.parent / "backend")
         if (b / "src" / "diakronos_app" / "frappe_compat" / "inventar" / "whitelist.json").exists()),
        None,
    )
    assert inventar is not None, "whitelist.json nicht gefunden"
    daten = json.loads(inventar.read_text(encoding="utf-8"))
    eintrag = next(e for e in daten["eintraege"]
                   if e["funktion"] == "diakronos_app.api.chat.personen_suchen")
    assert eintrag["einstufung"] == "lesend", eintrag
    assert eintrag["allow_guest"] is False
    # Widersprueche sind zulaessig, solange sie eine begruendete AUSNAHME
    # tragen (`ausnahme_greift`); „offen“ heisst: keine. Der Endpunkt selbst
    # taucht dort NICHT auf — er ist lesend, ohne Ausnahme.
    assert not [w for w in daten["widersprueche"]
                if w.get("offen") and w.get("funktion") == "diakronos_app.api.chat.personen_suchen"]
    # `ausnahmen_ohne_wirkung` ist eine Liste von Schluesseln (Strings).
    assert not [k for k in daten["ausnahmen_ohne_wirkung"]
                if "personen_suchen" in str(k)]


def test_gast_client_laesst_die_datenbank_unveraendert(welt, guest_client):
    """Zusatzbeweis zu SEC-11: die Suche schreibt nichts (Zeilen vorher/nachher)."""
    from diakronos_app.models.chat import ChatGespraech, ChatNachricht, ChatTeilnehmer

    def zaehlen() -> tuple[int, int, int]:
        s = welt
        return (s.query(ChatGespraech).count(), s.query(ChatNachricht).count(),
                s.query(ChatTeilnehmer).count())

    vorher = zaehlen()
    guest_client.get("/api/method/chat.personen_suchen", params={"q": "bert"})
    assert zaehlen() == vorher


def test_bild_wird_praefigiert_und_bei_geloeschten_geleert(welt):
    """``bild`` läuft über ``foto_mit_praefix`` (der EINE Präfigierer) und ist
    bei einer gelöschten Person leer."""
    from diakronos_app.api import chat as C

    assert C._suche_bild(None, False) == ""
    assert C._suche_bild("/files/bert.jpg", True) == ""
    wert = C._suche_bild("/files/bert.jpg", False)
    assert wert.endswith("/files/bert.jpg")


# ════════════════════════════════════════════════════════════════════════════
# Review 18.11.: Platzhalter, deaktiviertes Konto, Vorfilter blaettert
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("q", ["__", "%%", "_%", "\\\\"])
def test_like_platzhalter_finden_nicht_alle(welt, q):
    _set_user(ANNA)
    assert _suche(q=q)["treffer"] == []


def test_deaktiviertes_konto_gilt_als_kein_konto(welt):
    welt.get(User, BERT).enabled = 0
    welt.commit()
    _set_user(ANNA)
    t = _treffer(_suche(q="bert"), "M-Bert")
    assert t["hat_konto"] is False
    assert t["darf_schreiben"] is False


def test_viele_ausgetretene_schneiden_treffer_nicht_ab(welt, monkeypatch):
    from diakronos_app.api import chat as C

    monkeypatch.setattr(C, "_VORFILTER_MAX", 5)
    for i in range(12):
        konto = f"aus{i}@x.org"
        welt.add(User(name=konto, email=konto, enabled=1, full_name=f"A{i}"))
        # Nachname sortiert VOR „Zander…“: die ersten Seiten sind alle ausgetreten.
        welt.add(Mitglied(name=f"M-Aus{i:02d}", vorname="Zora", nachname=f"Aaa{i:02d}",
                          email=konto, user=konto, status="Ausgetreten"))
    welt.add(User(name="zora@x.org", email="zora@x.org", enabled=1, full_name="Zora"))
    welt.add(Mitglied(name="M-Zora", vorname="Zora", nachname="Zander",
                      email="zora@x.org", user="zora@x.org", status="Aktiv"))
    welt.commit()
    _set_user(ANNA)
    assert _kennungen(_suche(q="zora")) == ["M-Zora"]
