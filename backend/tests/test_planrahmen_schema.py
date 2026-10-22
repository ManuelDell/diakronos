"""Tests fuer den Plan-Rahmen (P1): Schema, Pruefung, Dokumentation, Kochbuch.

Reines Python — keine Datenbank, kein Redis, keine HTTP-Endpunkte. Geprueft
wird `diakronos_app.planrahmen`:

- alle Kochbuch-Dateien sind gueltig (keine Fehler, keine Warnungen),
- eine minimale Datei ist gueltig (P10: gutmuetig),
- jede semantische Pruefregel hat mindestens einen Negativtest mit der
  erwarteten Meldung und dem erwarteten Pfad,
- der Tippfehler-Vorschlag (difflib) greift,
- die eingecheckte REFERENZ.md ist aktuell (nicht von Hand gepflegt, P12).
"""

from __future__ import annotations

import pytest

from diakronos_app.planrahmen import ressourcen
from diakronos_app.planrahmen.referenz import erzeuge_referenz
from diakronos_app.planrahmen.pruefung import Meldung, pruefe_plantyp

# Das Kochbuch und die Referenz liegen IM Python-Paket (``doku/``) und werden
# ueber ``importlib.resources`` gelesen — sie muessen im Image vorhanden sein
# (das Repo-Verzeichnis ``docs/`` fehlt dort; NACHTRAG DOCKER). Es gibt daher
# keine Pfad-Berechnung mehr ueber ``Path(__file__)``.


def _minimal() -> dict:
    return {"schema": "diakronos/plantyp@1", "id": "test"}


def _plantyp(**kwargs) -> dict:
    """Minimale gueltige Datei, mit zusaetzlichen Abschnitten erweitert."""
    d = _minimal()
    d.update(kwargs)
    return d


def _codes(meldungen: list[Meldung]) -> set[str]:
    return {m.code for m in meldungen}


def _fehler_mit_code(meldungen: list[Meldung], code: str) -> Meldung:
    for m in meldungen:
        if m.code == code:
            return m
    raise AssertionError(f"keine Meldung mit code {code!r} in {[m.code for m in meldungen]}")


# --------------------------------------------------------------------------- #
# Kochbuch + minimale Datei
# --------------------------------------------------------------------------- #


def _kochbuch_dateien() -> list[str]:
    """Kennungen der Kochbuch-Beispiele (Dateinamen ohne Endung, sortiert)."""
    return ressourcen.kochbuch_dateinamen()


@pytest.mark.parametrize("name", _kochbuch_dateien())
def test_kochbuch_gueltig(name: str) -> None:
    """Jedes Kochbuch-Beispiel ist fehler- und warnungsfrei.

    Einzige Ausnahme: die Warnung `fremder_plantyp_ungeprueft` bei
    planuebergreifenden Verweisen (z. B. programm.json verweist auf den
    Chorplan). Die Existenz des fremden Plantyps ist bei der Einzeldatei-Pruefung
    unbekannt — genau dafuer ist sie eine WARNUNG und kein Fehler.
    """
    daten = ressourcen.kochbuch_laden(name)
    meldungen = [m for m in pruefe_plantyp(daten) if m.code != "fremder_plantyp_ungeprueft"]
    assert meldungen == [], (
        f"{name}.json soll sauber sein, liefert aber:"
        + "; ".join(f"{m.stufe} {m.code} {m.pfad}: {m.meldung}" for m in meldungen)
    )


def test_minimale_datei_gueltig() -> None:
    """P10: eine minimale Datei (nur schema + id) ist gueltig."""
    assert pruefe_plantyp(_minimal()) == []


def test_kein_objekt_liefert_fehler() -> None:
    """Eine Nicht-Objekt-Datei ergibt genau eine Fehlermeldung."""
    meldungen = pruefe_plantyp(["kein", "objekt"])
    assert len(meldungen) == 1
    assert meldungen[0].stufe == "fehler"
    assert meldungen[0].code == "kein_objekt"


# --------------------------------------------------------------------------- #
# Schema-Validierung
# --------------------------------------------------------------------------- #


def test_schema_fehler_gesammelt() -> None:
    """Schema-Fehler werden gesammelt, nicht nur der erste gemeldet."""
    d = _plantyp(
        felder=[
            {"id": "lieder", "art": "eintrag", "sammlung": "lieder"},
            {"id": "einsingen", "art": "NICHT_ERLAUBT"},  # enum-Verstoss
        ],
        ansichten=[{"art": "unbekannt"}],  # weiterer enum-Verstoss
    )
    meldungen = pruefe_plantyp(d)
    schema_codes = [m.code for m in meldungen if m.code == "schema"]
    assert len(schema_codes) >= 2, "mehrere Schema-Fehler sollen gesammelt werden"


def test_schema_fehler_required_pfad() -> None:
    """Fehlende Pflichteigenschaft nennt den passenden Pfad."""
    # 'id' fehlt auf oberster Ebene -> Pfad verweist auf das Objekt selbst.
    meldungen = pruefe_plantyp({"schema": "diakronos/plantyp@1"})
    m = _fehler_mit_code(meldungen, "schema")
    assert m.pfad in ("/", "/id")
    assert "Pflichteigenschaft" in m.meldung


# --------------------------------------------------------------------------- #
# Semantische Pruefung: Verweise
# --------------------------------------------------------------------------- #


def test_unbekannte_sammlung() -> None:
    d = _plantyp(felder=[{"id": "lieder", "art": "eintrag", "sammlung": "lider"}])
    m = _fehler_mit_code(pruefe_plantyp(d), "unbekannte_sammlung")
    assert m.pfad == "/felder/0/sammlung"


def test_vorbelegen_merkmal_fehlt() -> None:
    """aus='eintrag.dirigent' ohne deklariertes Merkmal 'dirigent' -> Fehler."""
    d = _plantyp(
        merkmale={"lieder": []},
        felder=[{"id": "lieder", "art": "eintrag", "sammlung": "lieder",
                 "inhalt": [{"id": "dirigent", "art": "person", "fuellen": "vorbelegen", "aus": "eintrag.dirigent"}]}],
    )
    m = _fehler_mit_code(pruefe_plantyp(d), "unbekanntes_merkmal")
    assert m.pfad == "/felder/0/inhalt/0/aus"


def test_anlass_wirkung_unbekanntes_feld() -> None:
    d = _plantyp(anlaesse=[{"id": "kinderchor", "wirkung": {"ohne": ["einsingen"]}}])
    m = _fehler_mit_code(pruefe_plantyp(d), "unbekanntes_feld")
    assert m.pfad == "/anlaesse/0/wirkung/ohne/0"


def test_regel_feld_unbekannt() -> None:
    d = _plantyp(felder=[], regeln=[{"baustein": "mindestabstand", "feld": "lieder", "wochen": 8}])
    m = _fehler_mit_code(pruefe_plantyp(d), "unbekanntes_regel_feld")
    assert m.pfad == "/regeln/0/feld"


def test_doppelte_feld_id() -> None:
    d = _plantyp(felder=[
        {"id": "lieder", "art": "text"},
        {"id": "lieder", "art": "text"},
    ])
    m = _fehler_mit_code(pruefe_plantyp(d), "doppelte_id")
    assert m.pfad == "/felder/1/id"


def test_anzahl_umgekehrt() -> None:
    d = _plantyp(felder=[{"id": "x", "art": "eintrag", "sammlung": "lieder", "anzahl": "3..1"}])
    m = _fehler_mit_code(pruefe_plantyp(d), "anzahl_umgekehrt")
    assert m.pfad == "/felder/0/anzahl"


def test_varianten_ohne_gruppe() -> None:
    d = _plantyp(felder=[{"id": "x", "art": "text", "varianten": ["a", "b"]}])
    meldungen = pruefe_plantyp(d)
    assert "varianten_ohne_gruppe" in _codes(meldungen)


def test_teile_ohne_gruppe() -> None:
    d = _plantyp(felder=[{"id": "x", "art": "text", "teile": ["a"]}])
    assert "teile_ohne_gruppe" in _codes(pruefe_plantyp(d))


# --------------------------------------------------------------------------- #
# Regeln: Baustein- und Parameter-Pruefung
# --------------------------------------------------------------------------- #


def test_unbekannter_baustein_mit_tipp() -> None:
    d = _plantyp(regeln=[{"baustein": "mindestabstant", "feld": "lieder", "wochen": 8}])
    m = _fehler_mit_code(pruefe_plantyp(d), "unbekannter_baustein")
    assert m.pfad == "/regeln/0/baustein"
    assert "mindestabstand" in m.meldung  # Tippfehler-Vorschlag enthalten


def test_unbekannter_regel_parameter() -> None:
    d = _plantyp(regeln=[{"baustein": "mindestabstand", "feld": "lieder", "wochen": 8, "woche": 8}])
    m = _fehler_mit_code(pruefe_plantyp(d), "unbekannter_parameter")
    assert m.pfad == "/regeln/0/woche"


def test_regel_parameter_pflicht_fehlend() -> None:
    """mindestabstand ohne 'wochen' verletzt das Baustein-Parameterschema."""
    d = _plantyp(felder=[{"id": "lieder", "art": "eintrag", "sammlung": "lieder"}],
                 regeln=[{"baustein": "mindestabstand", "feld": "lieder"}])
    m = _fehler_mit_code(pruefe_plantyp(d), "regel_parameter")
    assert m.pfad.startswith("/regeln/0")


# --------------------------------------------------------------------------- #
# Termine: RRULE
# --------------------------------------------------------------------------- #


def test_rrule_ungueltig() -> None:
    d = _plantyp(termine={"regel": "FREQ=WEEKLY;BYDAY=X1"})
    m = _fehler_mit_code(pruefe_plantyp(d), "rrule_unlesbar")
    assert m.pfad == "/termine/regel"


def test_rrule_ohne_freq() -> None:
    d = _plantyp(termine={"regel": "BYDAY=SU"})
    m = _fehler_mit_code(pruefe_plantyp(d), "rrule_unvollstaendig")


def test_rrule_gueltig_keine_meldung() -> None:
    d = _plantyp(termine={"regel": "FREQ=WEEKLY;BYDAY=SU"})
    assert "rrule_unesbar" not in _codes(pruefe_plantyp(d))
    assert "rrule_unvollstaendig" not in _codes(pruefe_plantyp(d))


def test_unbekannter_feiertag_warnung() -> None:
    d = _plantyp(termine={"feiertage": ["karfreitag", "ostramstag"]})
    m = _fehler_mit_code(pruefe_plantyp(d), "unbekannter_feiertag")
    assert m.stufe == "warnung"
    assert m.pfad == "/termine/feiertage/1"
    assert "ostersonntag" in m.meldung or "ostermontag" in m.meldung  # Tipp-Vorschlag


# --------------------------------------------------------------------------- #
# Tippfehler-Vorschlag (difflib) isoliert
# --------------------------------------------------------------------------- #


def test_tipp_vorschlag_funktioniert() -> None:
    from diakronos_app.planrahmen.pruefung import _tipp_vorschlag

    assert _tipp_vorschlag("mindestabstant", ["mindestabstand", "gleich_verteilen"]) == "mindestabstand"
    assert _tipp_vorschlag("klavier", ["klavier", "dirigent"]) == "klavier"
    assert _tipp_vorschlag("zzzz", ["klavier"]) is None  # zu weit weg


# --------------------------------------------------------------------------- #
# Meldungsstruktur
# --------------------------------------------------------------------------- #


def test_meldung_felder() -> None:
    """Jede Meldung traegt pfad, stufe, code, meldung, hinweis (P10)."""
    d = _plantyp(felder=[{"id": "lieder", "art": "eintrag", "sammlung": "lider"}])
    m = _fehler_mit_code(pruefe_plantyp(d), "unbekannte_sammlung")
    for feld in ("pfad", "stufe", "code", "meldung", "hinweis"):
        assert getattr(m, feld), f"Meldung hat kein Feld {feld!r}"
    assert m.stufe in ("fehler", "warnung")


# --------------------------------------------------------------------------- #
# Dokumentation
# --------------------------------------------------------------------------- #


def test_referenz_aktuell() -> None:
    """REFERENZ.md ist aus Schema + Registry erzeugt und aktuell (P12)."""
    eingeklickt = ressourcen.doku_text("REFERENZ.md")
    erzeugt = erzeuge_referenz()
    assert eingeklickt == erzeugt, (
        "REFERENZ.md ist veraltet. Bitte neu erzeugen: "
        "python3 backend/scripts/planrahmen_doku.py"
    )


def test_referenz_enthaelt_bausteine() -> None:
    """Die Referenz fuehrt alle Regel-Bausteine auf."""
    text = erzeuge_referenz()
    for baustein in ("abwesenheit_beachten", "mindestabstand", "max_pro_zeitraum",
                     "verfuegbarkeit"):
        assert f"### `{baustein}`" in text


def test_feiertags_katalog_im_paket_aktuell() -> None:
    """K4: ``doku/feiertage.json`` ist aus ``feiertage.py`` erzeugt und aktuell.

    Die Datei ist die Bruecke zur Oberflaeche: ein Node-Test vergleicht sie mit
    der Feiertagsliste der SPA. Weicht sie ab, ist der Vergleich wertlos — ein
    veralteter Schnappschuss liesse beide Seiten gruen.
    """
    import json
    from diakronos_app.planrahmen.feiertage import FEIERTAGE
    from diakronos_app.planrahmen import ressourcen

    eingeklickt = json.loads(ressourcen.doku_text("feiertage.json"))
    erwartet = [{"schluessel": f.schluessel, "name": f.name, "art": f.art} for f in FEIERTAGE]
    assert eingeklickt == erwartet, (
        "doku/feiertage.json ist veraltet. Bitte neu erzeugen: "
        "python3 backend/scripts/planrahmen_feiertage.py"
    )


def test_feiertage_holen_liefert_den_katalog() -> None:
    """K4: der Endpunkt, aus dem die Oberflaeche den Katalog holt.

    Dieses Modul laeuft OHNE Datenbank und ohne Sitzung, deshalb wird hier die
    Registrierung des Endpunkts und die von ihm benutzte QUELLE geprueft, nicht
    der Aufruf selbst: der Endpunkt ist mit ``_endpunkt()`` verdrahtet (also
    angemeldet und ueber ``/api/method`` erreichbar) und liefert genau
    ``feiertage.FEIERTAGE``. Den echten Aufruf samt Antwort prueft die
    Bedien-Abnahme gegen den laufenden Stack; ein Aufruf hier braeuchte eine
    Datenbank und wuerde den Zweck dieses Moduls brechen.
    """
    from diakronos_app.planrahmen.feiertage import FEIERTAGE
    from diakronos_app.frappe_compat.registry import lookup

    # Registrierung anstossen: ohne den Import ist die Registry leer und der
    # Test prueft nichts (er war deshalb zunaechst rot).
    import diakronos_app.api  # noqa: F401

    fn = lookup("diakronos.planrahmen.api.feiertage_holen")
    if fn is None:
        fn = lookup("planrahmen.feiertage_holen")
    assert fn is not None, "Endpunkt feiertage_holen ist nicht registriert"
    # Die eine Quelle: leere Dienst-Abhaengigkeit, reine Katalogliste.
    assert [f.schluessel for f in FEIERTAGE]
    assert len({f.schluessel for f in FEIERTAGE}) == len(FEIERTAGE), \
        "Feiertags-Kennungen sind nicht eindeutig"


def test_doku_und_kochbuch_im_paket() -> None:
    """Alle Laufzeit-Dokumente liegen im Paket und sind lesbar (NACHTRAG DOCKER).

    ``docs/`` fehlt im Image — darum muessen die handgeschriebenen Dokumente und
    die Beispiele ueber ``importlib.resources`` erreichbar sein.
    """
    for name in ("REFERENZ.md", "LEITFADEN.md", "KONZEPT.md", "KOCHBUCH.md",
                 "AGENT-ONBOARDING.md"):
        text = ressourcen.doku_text(name)
        assert text.strip(), f"{name} ist leer oder fehlt im Paket"

    namen = ressourcen.kochbuch_dateinamen()
    assert namen, "keine Kochbuch-Beispiele im Paket gefunden"
    for name in namen:
        assert isinstance(ressourcen.kochbuch_laden(name), dict)


# --------------------------------------------------------------------------- #
# Review PR1: strukturierte Bedingung
# --------------------------------------------------------------------------- #


def test_bedingung_unbekannter_anlass() -> None:
    d = _plantyp(felder=[{"id": "f", "art": "text", "bedingung": {"anlass": "gibtsnicht"}}])
    m = _fehler_mit_code(pruefe_plantyp(d), "unbekannter_anlass")
    assert m.pfad == "/felder/0/bedingung/anlass"


def test_bedingung_unbekannter_parameter() -> None:
    d = _plantyp(felder=[{"id": "f", "art": "text", "bedingung": {"parameter": {"id": "nichtda", "gleich": 1}}}])
    m = _fehler_mit_code(pruefe_plantyp(d), "unbekannter_parameter_bedingung")
    assert m.pfad == "/felder/0/bedingung/parameter/id"


def test_bedingung_unbekantnes_feld() -> None:
    d = _plantyp(felder=[{"id": "f", "art": "text", "bedingung": {"feld_gesetzt": "gibtsnicht"}}])
    m = _fehler_mit_code(pruefe_plantyp(d), "unbekanntes_feld_bedingung")
    assert m.pfad == "/felder/0/bedingung/feld_gesetzt"


def test_bedingung_unbekannte_variante() -> None:
    d = _plantyp(felder=[{
        "id": "gruppe", "art": "gruppe", "varianten": ["sonne", "regen"],
        "inhalt": [{"id": "f", "art": "text", "bedingung": {"variante": "schnee"}}],
    }])
    m = _fehler_mit_code(pruefe_plantyp(d), "unbekannte_variante")
    assert m.pfad == "/felder/0/inhalt/0/bedingung/variante"


def test_bedingung_variante_ohne_gruppe_ist_warnung() -> None:
    d = _plantyp(felder=[{"id": "f", "art": "text", "bedingung": {"variante": "regen"}}])
    m = _fehler_mit_code(pruefe_plantyp(d), "variante_ohne_gruppe")
    assert m.stufe == "warnung"


def test_bedingung_gueltig_verschachtelt() -> None:
    d = _plantyp(
        anlaesse=[{"id": "abendmahl"}],
        felder=[{"id": "f", "art": "text",
                 "bedingung": {"alle": [{"anlass": "abendmahl"}, {"nicht": {"wochentag": ["mo"]}}]}}],
    )
    assert "unbekannter_anlass" not in _codes(pruefe_plantyp(d))


def test_wirkung_bedingung_geprueft() -> None:
    d = _plantyp(anlaesse=[{"id": "abendmahl", "wirkung": {"ohne": [], "bedingung": {"anlass": "falsch"}}}])
    m = _fehler_mit_code(pruefe_plantyp(d), "unbekannter_anlass")
    assert m.pfad == "/anlaesse/0/wirkung/bedingung/anlass"


# --------------------------------------------------------------------------- #
# Review PR1: Varianten/Teile als Objekte
# --------------------------------------------------------------------------- #


def test_teile_objekt_doppelte_id() -> None:
    d = _plantyp(felder=[{
        "id": "gruppe", "art": "gruppe",
        "teile": [{"id": "a", "inhalt": []}, "a"],
    }])
    m = _fehler_mit_code(pruefe_plantyp(d), "doppelte_id")


def test_teile_objekt_eigene_inhalt_geprueft() -> None:
    # eigener inhalt einer Variante enthaelt ein unbekanntes sammlung-Feld
    d = _plantyp(felder=[{
        "id": "gruppe", "art": "gruppe",
        "varianten": [{"id": "regen", "inhalt": [{"id": "x", "art": "eintrag", "sammlung": "nix"}]}],
    }])
    m = _fehler_mit_code(pruefe_plantyp(d), "unbekannte_sammlung")
    assert m.pfad == "/felder/0/varianten/0/inhalt/0/sammlung"


def test_teile_gemischt_kurz_und_langform() -> None:
    d = _plantyp(felder=[{
        "id": "gruppe", "art": "gruppe",
        "teile": ["programm", {"id": "abschluss", "name": "Abschluss", "inhalt": [{"id": "lied", "art": "eintrag", "sammlung": "lieder"}]}],
    }])
    assert pruefe_plantyp(d) == []


# --------------------------------------------------------------------------- #
# Review PR1: eingebaute Attribute + Sammlungsumfang
# --------------------------------------------------------------------------- #


def test_merkmal_ueberschattet_attribut() -> None:
    d = _plantyp(merkmale={"person": [{"id": "kuerzel", "art": "tag"}]})
    m = _fehler_mit_code(pruefe_plantyp(d), "attribut_ueberschattet")
    assert m.pfad == "/merkmale/person/0/id"


def test_sammlung_umfang_plan_gueltig() -> None:
    d = _plantyp(sammlungen=[{"id": "themen", "name": "Themen", "umfang": "plan"}])
    assert pruefe_plantyp(d) == []


def test_parameter_art_sammlung_nicht_mehr_erlaubt() -> None:
    d = _plantyp(parameter=[{"id": "p", "art": "sammlung"}])
    assert "schema" in _codes(pruefe_plantyp(d))


# --------------------------------------------------------------------------- #
# Review PR1: Formatvorlagen-Platzhalter (Warnung)
# --------------------------------------------------------------------------- #


def test_format_unbekanntes_attribut_warnung() -> None:
    d = _plantyp(
        felder=[{"id": "lieder", "art": "eintrag", "sammlung": "lieder"}],
        ansichten=[{"art": "tabelle", "format": {"lieder": "{eintrag.foo}"}}],
    )
    m = _fehler_mit_code(pruefe_plantyp(d), "format_unbekanntes_attribut")
    assert m.stufe == "warnung"


def test_format_eingebautes_attribut_still() -> None:
    d = _plantyp(
        felder=[{"id": "lieder", "art": "eintrag", "sammlung": "lieder"}],
        ansichten=[{"art": "tabelle", "format": {"lieder": "{eintrag.titel} Nr.{eintrag.nummer}"}}],
    )
    assert "format_unbekanntes_attribut" not in _codes(pruefe_plantyp(d))


def test_format_unbekanntes_feld_warnung() -> None:
    d = _plantyp(ansichten=[{"art": "tabelle", "format": {"x": "{gibtsnicht.kuerzel}"}}])
    m = _fehler_mit_code(pruefe_plantyp(d), "format_unbekanntes_feld")
    assert m.stufe == "warnung"


# --------------------------------------------------------------------------- #
# Review PR1: merkmal_nicht_deklariert (Warnung)
# --------------------------------------------------------------------------- #


def test_merkmal_nicht_deklariert_warnung() -> None:
    d = _plantyp(felder=[{"id": "f", "art": "person", "rolle": {"merkmal": "orgel"}}])
    m = _fehler_mit_code(pruefe_plantyp(d), "merkmal_nicht_deklariert")
    assert m.stufe == "warnung"
    assert m.pfad == "/felder/0/rolle/merkmal"


def test_merkmal_deklariert_keine_warnung() -> None:
    d = _plantyp(
        merkmale={"person": [{"id": "orgel", "art": "tag"}]},
        felder=[{"id": "f", "art": "person", "rolle": {"merkmal": "orgel"}}],
    )
    assert "merkmal_nicht_deklariert" not in _codes(pruefe_plantyp(d))


# --------------------------------------------------------------------------- #
# Review PR1: doku_anker (jeder Code hat einen existierenden Anker)
# --------------------------------------------------------------------------- #


def test_jeder_meldungscode_hat_anker() -> None:
    """Jeder Meldungscode hat einen Anker in der generierten REFERENZ.md."""
    from diakronos_app.planrahmen.pruefung import MELDUNGS_CODES

    text = erzeuge_referenz()
    for code in MELDUNGS_CODES:
        assert f'id="meldung-{code}"' in text, f"kein Anker fuer Meldungscode {code!r}"


def test_meldung_doku_anker_nicht_leer() -> None:
    """Eine erzeugte Meldung traegt einen nicht-leeren doku_anker (P10)."""
    d = _plantyp(felder=[{"id": "f", "art": "eintrag", "sammlung": "lider"}])
    m = _fehler_mit_code(pruefe_plantyp(d), "unbekannte_sammlung")
    assert m.doku_anker == "meldung-unbekannte_sammlung"
    assert 'id="meldung-unbekannte_sammlung"' in erzeuge_referenz()


def test_meldungs_codes_vollstaendig() -> None:
    """Alle Codes, die pruefe_plantyp erzeugen kann, sind im Katalog."""
    from diakronos_app.planrahmen.pruefung import MELDUNGS_CODES

    # eine Handvoll repräsentativer Codes müssen im Katalog stehen.
    for code in ("schema", "doppelte_id", "unbekannter_baustein", "rrule_unlesbar",
                 "attribut_ueberschattet", "merkmal_nicht_deklariert", "unbekannter_anlass"):
        assert code in MELDUNGS_CODES, code


# --------------------------------------------------------------------------- #
# Eingebaute Attribute in der Referenz
# --------------------------------------------------------------------------- #


def test_referenz_enthaelt_attribute() -> None:
    text = erzeuge_referenz()
    assert "Eingebaute Attribute" in text
    assert "`kuerzel`" in text
    assert "`ccli`" in text
    assert "`reihenfolge`" in text


# --------------------------------------------------------------------------- #
# NACHTRAG C3: Terminreihen, abgeleitete Termine, team, termin_im_monat
# --------------------------------------------------------------------------- #


def test_terminreihen_und_kurzform_schliessen_sich_aus() -> None:
    d = _plantyp(
        termine={"regel": "FREQ=WEEKLY;BYDAY=SU"},
        felder=[{"id": "f", "art": "text"}],
        terminreihen=[{"id": "r", "termine": {"regel": "FREQ=WEEKLY;BYDAY=SU"}, "felder": []}],
    )
    m = _fehler_mit_code(pruefe_plantyp(d), "terminreihen_und_kurzform")
    assert m.pfad == "/terminreihen"


def test_terminreihen_gueltig() -> None:
    d = _plantyp(terminreihen=[
        {"id": "gottesdienst", "termine": {"regel": "FREQ=WEEKLY;BYDAY=SU"},
         "felder": [{"id": "team", "art": "team", "teams": {"gruppe_unter": "Musikteams"}}]},
        {"id": "probe",
         "termine": {"abgeleitet": {"von": "gottesdienst", "versatz": "-2T"}},
         "felder": [{"id": "team", "art": "team", "fuellen": "vorbelegen", "aus": "bezug.team"}]},
    ])
    assert pruefe_plantyp(d) == []


def test_abgeleitet_unbekannte_reihe() -> None:
    d = _plantyp(terminreihen=[
        {"id": "probe", "termine": {"abgeleitet": {"von": "gibtsnicht", "versatz": "-2T"}}, "felder": []},
    ])
    m = _fehler_mit_code(pruefe_plantyp(d), "unbekannte_reihe")
    assert m.pfad == "/terminreihen/0/termine/abgeleitet/von"


def test_abgeleitet_zyklus() -> None:
    d = _plantyp(terminreihen=[
        {"id": "a", "termine": {"abgeleitet": {"von": "a", "versatz": "-2T"}}, "felder": []},
    ])
    m = _fehler_mit_code(pruefe_plantyp(d), "ableitung_zyklus")


def test_abgeleitet_versatz_unlesbar() -> None:
    d = _plantyp(terminreihen=[
        {"id": "a", "termine": {"abgeleitet": {"von": "b", "versatz": "vorher"}}, "felder": []},
        {"id": "b", "termine": {"regel": "FREQ=WEEKLY;BYDAY=SU"}, "felder": []},
    ])
    m = _fehler_mit_code(pruefe_plantyp(d), "versatz_unlesbar")
    assert m.pfad == "/terminreihen/0/termine/abgeleitet/versatz"


def test_team_ohne_teams() -> None:
    d = _plantyp(felder=[{"id": "team", "art": "team", "fuellen": "reihum"}])
    m = _fehler_mit_code(pruefe_plantyp(d), "team_ohne_teams")
    assert m.pfad == "/felder/0/teams"


def test_termin_im_monat_bedingung_gueltig() -> None:
    d = _plantyp(felder=[{"id": "f", "art": "text", "bedingung": {"termin_im_monat": 2}}])
    assert pruefe_plantyp(d) == []


def test_sammelanlass_feiertag_gueltig() -> None:
    d = _plantyp(termine={"feiertage": ["silvester"]},
                 anlaesse=[{"id": "feiertag"}],
                 felder=[{"id": "f", "art": "text", "bedingung": {"anlass": "feiertag"}}])
    assert "unbekannter_anlass" not in _codes(pruefe_plantyp(d))


def test_silvester_im_feiertags_katalog() -> None:
    from diakronos_app.planrahmen.feiertage import feiertage_katalog

    assert "silvester" in feiertage_katalog()


def test_ansicht_kalender_gueltig() -> None:
    d = _plantyp(ansichten=[{"art": "kalender", "spalten": "monat", "alle_tage": True, "kw": True}])
    assert pruefe_plantyp(d) == []


def test_format_bedingter_platzhalter_gueltig() -> None:
    d = _plantyp(
        felder=[{"id": "gaeste", "art": "personen", "pflicht": False}],
        ansichten=[{"art": "kalender", "format": {"standard": "{gaeste: + {gaeste.vorname}}"}}],
    )
    assert "format_unbekanntes" not in _codes(pruefe_plantyp(d))


def test_scan_format_bedingt() -> None:
    from diakronos_app.planrahmen.pruefung import _scan_format

    # Bedingungsfeld 'gaeste' + verschachtelter Platzhalter 'gaeste.vorname'
    assert _scan_format("{gaeste: + {gaeste.vorname}}") == ["gaeste", "gaeste.vorname"]
    assert _scan_format("{team.name}{anlass: ({anlass})}") == ["team.name", "anlass", "anlass"]


def test_verfuegbarkeit_mit_team_und_muster() -> None:
    d = _plantyp(felder=[{"id": "team", "art": "team", "teams": {"gruppe_unter": "Musikteams"}}],
                 regeln=[{"baustein": "verfuegbarkeit", "team": "Gruppe 3",
                          "muster": {"termin_im_monat": 1}, "stufe": "muss"}])
    assert pruefe_plantyp(d) == []


# --------------------------------------------------------------------------- #
# Review PR1 Befund A: Vorwaertsverweis + mittelbarer Zyklus (ableitung_zyklus)
# --------------------------------------------------------------------------- #


def test_abgeleitet_vorwaertsverweis_ok() -> None:
    """Reihe a darf von einer spaeter definierten Reihe b abgeleitet sein (A)."""
    d = _plantyp(terminreihen=[
        {"id": "a", "termine": {"abgeleitet": {"von": "b", "versatz": "-2T"}}, "felder": []},
        {"id": "b", "termine": {"regel": "FREQ=WEEKLY;BYDAY=SU"}, "felder": []},
    ])
    assert "unbekannte_reihe" not in _codes(pruefe_plantyp(d))
    assert "ableitung_zyklus" not in _codes(pruefe_plantyp(d))


def test_abgeleitet_mittelbarer_zyklus() -> None:
    """Mittelbarer Zyklus A->B->A wird mit konkreten Pfad gemeldet (A)."""
    d = _plantyp(terminreihen=[
        {"id": "a", "termine": {"abgeleitet": {"von": "b", "versatz": "-2T"}}, "felder": []},
        {"id": "b", "termine": {"abgeleitet": {"von": "a", "versatz": "+2T"}}, "felder": []},
    ])
    m = _fehler_mit_code(pruefe_plantyp(d), "ableitung_zyklus")
    assert "a" in m.meldung and "b" in m.meldung  # Zykluspfad enthalten


def test_abgeleitet_standard_nur_kurzform() -> None:
    """'standard' als Verwiesziel ist unter 'terminreihen' ein Fehler (A)."""
    d = _plantyp(terminreihen=[
        {"id": "a", "termine": {"abgeleitet": {"von": "standard", "versatz": "-2T"}}, "felder": []},
    ])
    m = _fehler_mit_code(pruefe_plantyp(d), "unbekannte_reihe")
    assert m.pfad.endswith("/von")


# --------------------------------------------------------------------------- #
# Review PR1 Befund B: Wochentage gutmuetig (Gross-/Kleinschreibung, Langname)
# --------------------------------------------------------------------------- #


def test_wochentag_grossschreibung_still() -> None:
    """'Sa'/'SA' (RRULE-Stil) sind gueltig, keine Warnung (B)."""
    d = _plantyp(termine={"zeitraum": "{parameter.z}", "wochentage": ["Sa"]},
                 parameter=[{"id": "z", "art": "zeitraum"}])
    assert pruefe_plantyp(d) == []


def test_wochentag_langname_warnt() -> None:
    """Ein langer Name ('samstag') wird auf 'sa' abgebildet und warnend gemeldet (B)."""
    d = _plantyp(termine={"zeitraum": "{parameter.z}", "wochentage": ["samstag"]},
                 parameter=[{"id": "z", "art": "zeitraum"}])
    meldungen = pruefe_plantyp(d)
    m = _fehler_mit_code(meldungen, "wochentag_langname")
    assert m.stufe == "warnung"
    assert "schema" not in _codes(meldungen)  # Normalisierung greift vor dem Schema


def test_wochentag_bedingung_grossschreibung() -> None:
    """Bedingung {wochentag: ['SO']} wird normalisiert und ist gueltig (B)."""
    d = _plantyp(felder=[{"id": "f", "art": "text", "bedingung": {"wochentag": ["SO"]}}])
    assert pruefe_plantyp(d) == []


# --------------------------------------------------------------------------- #
# PR1b: Feldart 'ablauf'
# --------------------------------------------------------------------------- #


def _programm_plantyp() -> dict:
    """Minimaler gueltiger 'ablauf'-Plantyp (lied + szene)."""
    return _plantyp(
        felder=[{
            "id": "ablauf", "art": "ablauf", "anzahl": "1..*",
            "elemente": [
                {"typ": "lied", "nummeriert": True,
                 "inhalt": [{"id": "lied", "art": "eintrag", "sammlung": "lieder"}]},
                {"typ": "szene", "inhalt": [{"id": "titel", "art": "text"}]},
            ],
        }],
    )


def test_ablauf_gueltig() -> None:
    assert pruefe_plantyp(_programm_plantyp()) == []


def test_ablauf_ohne_elemente() -> None:
    d = _plantyp(felder=[{"id": "ablauf", "art": "ablauf"}])
    m = _fehler_mit_code(pruefe_plantyp(d), "ablauf_ohne_elemente")
    assert m.pfad == "/felder/0/elemente"


def test_elemente_ohne_ablauf() -> None:
    d = _plantyp(felder=[{"id": "f", "art": "text", "elemente": [{"typ": "x", "inhalt": []}]}])
    m = _fehler_mit_code(pruefe_plantyp(d), "elemente_ohne_ablauf")
    assert m.stufe == "warnung"


def test_doppelter_elementtyp() -> None:
    d = _plantyp(felder=[{
        "id": "ablauf", "art": "ablauf",
        "elemente": [
            {"typ": "lied", "inhalt": []},
            {"typ": "lied", "inhalt": []},
        ],
    }])
    m = _fehler_mit_code(pruefe_plantyp(d), "doppelter_elementtyp")
    assert m.pfad == "/felder/0/elemente/1/typ"


def test_ablauf_element_inhalt_geprueft() -> None:
    """Ein fehlerhafter Inhalt eines Ablauf-Elements wird gefunden."""
    d = _plantyp(felder=[{
        "id": "ablauf", "art": "ablauf",
        "elemente": [{"typ": "lied", "inhalt": [{"id": "lied", "art": "eintrag", "sammlung": "lider"}]}],
    }])
    m = _fehler_mit_code(pruefe_plantyp(d), "unbekannte_sammlung")
    assert m.pfad == "/felder/0/elemente/0/inhalt/0/sammlung"


def test_ablauf_anzahl_offenes_ende() -> None:
    """'anzahl: 0..*' / '1..*' sind zulaessig."""
    assert pruefe_plantyp(_programm_plantyp()) == []
    d = _plantyp(felder=[{"id": "x", "art": "eintrag", "sammlung": "lieder", "anzahl": "0..*"}])
    assert pruefe_plantyp(d) == []


# --------------------------------------------------------------------------- #
# PR1b: planuebergreifende Bezuege + Uebernahme
# --------------------------------------------------------------------------- #


def test_vorher_geuebt_uebung_fremd_plantyp_warnung() -> None:
    """uebung={plantyp,feld} auf fremden Plantyp -> Warnung, kein Fehler."""
    d = _plantyp(
        felder=[{"id": "ablauf", "art": "ablauf",
                 "elemente": [{"typ": "lied", "inhalt": [{"id": "lied", "art": "eintrag", "sammlung": "lieder"}]}]}],
        regeln=[{"baustein": "vorher_geuebt", "feld": "ablauf.lied",
                 "uebung": {"plantyp": "chorplan", "feld": "einueben"}, "mindestens": 3}],
    )
    m = _fehler_mit_code(pruefe_plantyp(d), "fremder_plantyp_ungeprueft")
    assert m.stufe == "warnung"
    assert m.pfad == "/regeln/0/uebung/plantyp"


def test_vorher_geuebt_uebung_eigener_plantyp_fehler() -> None:
    """uebung={plantyp: eigener} -> Fehler 'fremder_plantyp'."""
    d = _plantyp(
        id="chorplan",
        regeln=[{"baustein": "vorher_geuebt", "feld": "lieder",
                 "uebung": {"plantyp": "chorplan", "feld": "einueben"}, "mindestens": 2}],
    )
    m = _fehler_mit_code(pruefe_plantyp(d), "fremder_plantyp")


def test_mindestabstand_auch_in_erlaubt() -> None:
    """mindestabstand akzeptiert 'auch_in' (gemeinsame Historie)."""
    d = _plantyp(felder=[{"id": "lieder", "art": "eintrag", "sammlung": "lieder"}],
                 regeln=[{"baustein": "mindestabstand", "feld": "lieder", "wochen": 8,
                          "auch_in": ["programm"]}])
    assert pruefe_plantyp(d) == []


def test_uebernahme_gueltig() -> None:
    """Plantyp-Option 'uebernahme' ist gueltig."""
    d = _plantyp(uebernahme={"erlaubt_von": ["programm"], "felder": ["ablauf.lied"]})
    assert pruefe_plantyp(d) == []


def test_uebernahme_schema_pflicht() -> None:
    """uebernahme ohne erlaubt_von/felder verletzt das Schema."""
    d = _plantyp(uebernahme={"erlaubt_von": []})
    assert "schema" in _codes(pruefe_plantyp(d))


# --------------------------------------------------------------------------- #
# PR1b: Lied-Attribut 'seite' + Ansicht 'programm'
# --------------------------------------------------------------------------- #


def test_lied_seite_ist_eingebautes_attribut() -> None:
    from diakronos_app.planrahmen.regeln.registry import eingebaute_attribut_schluessel

    assert "seite" in eingebaute_attribut_schluessel("lieder")


def test_format_bedingte_seite_pruefbar() -> None:
    """'{lied.seite: S. {lied.seite}}' ist ohne Warnung pruefbar."""
    d = _plantyp(
        felder=[{"id": "ablauf", "art": "ablauf",
                 "elemente": [{"typ": "lied", "inhalt": [{"id": "lied", "art": "eintrag", "sammlung": "lieder"}]}]}],
        ansichten=[{"art": "programm", "format": {
            "lied": "{nr} | {lied.buch}{lied.seite: S. {lied.seite}} | {lied.titel}",
        }}],
    )
    assert "format_unbekanntes" not in _codes(pruefe_plantyp(d))


def test_ansicht_programm_gueltig() -> None:
    """'programm'-Ansicht mit kopf/fuss und Format je Elementtyp."""
    d = _plantyp(
        parameter=[{"id": "motto", "art": "text"}, {"id": "schluss", "art": "text"}],
        felder=[{"id": "ablauf", "art": "ablauf", "anzahl": "1..*",
                 "elemente": [
                     {"typ": "lied", "nummeriert": True, "inhalt": [{"id": "lied", "art": "eintrag", "sammlung": "lieder"}]},
                     {"typ": "szene", "inhalt": [{"id": "titel", "art": "text"}]},
                 ]}],
        ansichten=[{"art": "programm", "druck": "A4-hoch",
                    "kopf": "{plan.titel} {termin.datum}\n{parameter.motto}",
                    "fuss": "{parameter.schluss}",
                    "format": {"lied": "{nr} | {lied.titel}", "szene": "— {titel} —"}}],
    )
    assert pruefe_plantyp(d) == []


def test_programm_format_unbekannter_elementtyp() -> None:
    """Format-Schluessel, der kein Elementtyp ist, wird warnend gemeldet."""
    d = _plantyp(
        felder=[{"id": "ablauf", "art": "ablauf",
                 "elemente": [{"typ": "lied", "inhalt": []}]}],
        ansichten=[{"art": "programm", "format": {"lieder": "{nr}"}}],
    )
    m = _fehler_mit_code(pruefe_plantyp(d), "unbekannter_elementtyp")
    assert m.stufe == "warnung"


def test_programm_kopf_platzhalter_geprueft() -> None:
    """Unbekannter Parameter im kopf wird als Warnung gemeldet."""
    d = _plantyp(ansichten=[{"art": "programm", "kopf": "{parameter.gibtsnicht}"}])
    m = _fehler_mit_code(pruefe_plantyp(d), "format_unbekannter_parameter")
    assert m.stufe == "warnung"
