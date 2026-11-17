"""DEV-B4a — Beziehungen eintragen/entfernen (Befund DMB-72325633c6b5).

Vorher zeigte `MitgliedDetail.vue` den Reiter „Beziehungen" nur lesend; im
Bearbeitungsmodus gab es keinen Weg, eine Beziehung einzutragen oder zu
entfernen. Diese Datei prueft den Server-Weg
(`diakronos_app/api/beziehungen.py`) Punkt fuer Punkt gegen die Kartenregeln:

  * Recht wie „Mitglied bearbeiten" (kein Edit -> PermissionError),
  * Gegenrichtung automatisch + `ist_spiegel=1` (wie der Altcode-Hook),
  * keine Doppelung, keine Selbstbeziehung,
  * Entfernen raeumt BEIDE Richtungen ab und nennt, was zum Wiederherstellen
    noetig ist („Zuruecknehmen", UX2c),
  * jede Aenderung steht im Audit-Protokoll,
  * die Auswahlliste bietet die eigene Person nicht an und sucht nicht in
    der E-Mail (B-1).

Diese Tests sind gegen den Stand VOR dem Fix rot (die Endpunkte existierten
nicht) und danach gruen.
"""
from __future__ import annotations

import pytest

from diakronos_app.frappe_compat.exceptions import (
    DoesNotExistError,
    PermissionError,
    ValidationError,
)
from diakronos_app.frappe_compat.session import set_user
from diakronos_app.models.core import HasRole, User
from diakronos_app.models.diakonos import Mitglied, MitgliedBeziehung

MA = "Mitgliederadministrator"

# Kennungen wie im Betrieb: Konto = E-Mail, Mitglied = „M-<konto>".
ADMIN = "verwaltung@x.org"
MITGLIED = "lena@x.org"
ANNA = "M-anna@x.org"
BRUNO = "M-bruno@x.org"
CLARA = "M-clara@x.org"


def _konto(sess, kennung: str, rolle: str | None = None, *,
           vorname: str = "Lena", nachname: str = "Leser", konto: str | None = None) -> None:
    konto = konto or kennung
    # `mitglied_permissions` antwortet Nicht-Admins je `ancestor_path`: dieselbe
    # Gruppe fuer alle, damit Sicht und Bearbeiten wie im Betrieb greifen.
    sess.add(User(name=konto, email=konto, full_name=konto, enabled=True))
    if rolle:
        sess.add(HasRole(name=f"HR-{kennung}-{rolle}", parent=konto,
                         parenttype="User", parentfield="roles", role=rolle,
                         docstatus=0, idx=1))
    sess.add(Mitglied(
        name=f"M-{konto}", vorname=vorname, nachname=nachname,
        email=konto, status="Mitglied",
        # Konten verknuepft nur der Administrator: Nicht-Admins haben keins,
        # sonst greift der Selbst-Schreibzugriff (Ueberlappung mit sich selbst).
        user=konto if rolle else None,
        ausgeschlossen=0, docstatus=0, idx=0,
        ancestor_path="/G-1/|/DB-A/",
    ))
    sess.commit()


@pytest.fixture()
def welt(patched_db):
    """Administrator, einfaches Mitglied und drei weitere Personen."""
    sess = patched_db()
    _konto(sess, ADMIN, MA)
    _konto(sess, "lena", vorname="Lena", nachname="Leser", konto=MITGLIED)
    _konto(sess, "anna", vorname="Anna", nachname="Beispiel", konto="anna@x.org")
    _konto(sess, "bruno", vorname="Bruno", nachname="Beispiel", konto="bruno@x.org")
    _konto(sess, "clara", vorname="Clara", nachname="Beispiel", konto="clara@x.org")
    yield sess
    sess.close()
    set_user("Administrator")


def _zeilen(sess, parent: str) -> list[MitgliedBeziehung]:
    sess.expire_all()
    return [
        z for z in sess.query(MitgliedBeziehung).filter_by(parent=parent).all()
    ]


def _paar(sess, a: str, b: str):
    return [z for z in _zeilen(sess, a) if z.beziehung_zu == b]


def _audit_zeilen(sess) -> list[dict]:
    from diakronos_app.frappe_compat.query import get_all

    sess.expire_all()
    return get_all("Audit Log", filters={"target_doctype": "Mitglied"},
                   fields=["action_typ", "target_name", "begruendung", "actor"])


# ── Eintragen: Gegenrichtung, Spiegel-Marke, Audit ──────────────────────────


def test_add_legt_beide_richtungen_an(welt) -> None:
    from diakronos_app.api.beziehungen import add_beziehung

    sess = welt
    set_user(ADMIN)
    antwort = add_beziehung(ANNA, BRUNO, "Kind")

    assert antwort["success"] is True
    assert antwort["bestand"] is False
    # A -> B „Kind"
    hin = _paar(sess, ANNA, BRUNO)
    assert len(hin) == 1
    assert hin[0].beziehungstyp == "Kind"
    assert bool(hin[0].ist_spiegel) is False
    assert hin[0].parentfield == "beziehungen"
    # B -> A „Elternteil" (Gegenrichtung, als Spiegel markiert)
    her = _paar(sess, BRUNO, ANNA)
    assert len(her) == 1
    assert her[0].beziehungstyp == "Elternteil"
    assert bool(her[0].ist_spiegel) is True
    # Das Protokoll nennt beide Namen — nicht nur Kennungen.
    eintrag = [z for z in _audit_zeilen(sess) if "Beziehung eingetragen" in z["begruendung"]]
    assert len(eintrag) == 1
    assert "Bruno Beispiel" in eintrag[0]["begruendung"]
    assert eintrag[0]["action_typ"] == "Profiländerung"
    assert eintrag[0]["target_name"] == ANNA


def test_add_ist_symmetrisch_fuer_ehepartner(welt) -> None:
    from diakronos_app.api.beziehungen import add_beziehung

    sess = welt
    set_user(ADMIN)
    add_beziehung(ANNA, CLARA, "Ehepartner")
    assert [z.beziehungstyp for z in _paar(sess, ANNA, CLARA)] == ["Ehepartner"]
    assert [z.beziehungstyp for z in _paar(sess, CLARA, ANNA)] == ["Ehepartner"]


def test_add_doppelt_wird_abgelehnt(welt) -> None:
    from diakronos_app.api.beziehungen import add_beziehung

    sess = welt
    set_user(ADMIN)
    add_beziehung(ANNA, BRUNO, "Kind")
    with pytest.raises(ValidationError) as fehler:
        add_beziehung(ANNA, BRUNO, "Kind")
    assert "besteht bereits" in str(fehler.value)
    assert len(_paar(sess, ANNA, BRUNO)) == 1
    assert len(_paar(sess, BRUNO, ANNA)) == 1

    # Auch mit ANDERER Art keine zweite Wahrheit zwischen denselben Personen.
    with pytest.raises(ValidationError):
        add_beziehung(ANNA, BRUNO, "Geschwister")
    assert len(_paar(sess, ANNA, BRUNO)) == 1


def test_add_von_der_anderen_seite_ist_keine_doppelung(welt) -> None:
    """B→A zuerst: danach lehnt A→B ab und nennt die Gegenrichtung.

    Review 10.11.: Die Beziehung ist symmetrisch — es gibt je Personenpaar
    genau eine Aussage, also legt A→B nichts mehr an, wenn B→A schon steht.
    """
    from diakronos_app.api.beziehungen import add_beziehung

    sess = welt
    set_user(ADMIN)
    add_beziehung(BRUNO, ANNA, "Elternteil")
    assert len(_paar(sess, BRUNO, ANNA)) == 1
    with pytest.raises(ValidationError) as fehler:
        add_beziehung(ANNA, BRUNO, "Kind")
    assert "von der anderen Seite als „Elternteil“" in str(fehler.value)
    assert len(_paar(sess, ANNA, BRUNO)) == 1
    assert len(_paar(sess, BRUNO, ANNA)) == 1


def test_add_nennt_die_andere_art_von_der_gegenseite(welt) -> None:
    """Steht dort eine ANDERE Art, sagt die Meldung welche (Review 10.11.)."""
    from diakronos_app.api.beziehungen import add_beziehung

    sess = welt
    set_user(ADMIN)
    add_beziehung(BRUNO, ANNA, "Geschwister")
    with pytest.raises(ValidationError) as fehler:
        add_beziehung(ANNA, BRUNO, "Kind")
    assert "von der anderen Seite als „Geschwister“" in str(fehler.value)
    # A→B hat NICHTS angelegt; A hat nur die Spiegelzeile aus B→A.
    assert [z.beziehungstyp for z in _paar(sess, BRUNO, ANNA)] == ["Geschwister"]
    assert all(bool(z.ist_spiegel) for z in _paar(sess, ANNA, BRUNO))


def test_add_gleiche_aussage_ueber_spiegel_heisst_besteht_bereits(welt) -> None:
    """B→A „Kind" steht; A→B „Elternteil" ist DIESELBE Aussage (Re-Review 10.11.)."""
    from diakronos_app.api.beziehungen import add_beziehung

    sess = welt
    set_user(ADMIN)
    add_beziehung(BRUNO, ANNA, "Kind")
    with pytest.raises(ValidationError) as fehler:
        add_beziehung(ANNA, BRUNO, "Elternteil")
    text = str(fehler.value)
    assert "besteht bereits von der anderen Seite als „Kind“" in text
    assert "zuerst entfernen" not in text
    assert [z.beziehungstyp for z in _paar(sess, BRUNO, ANNA)] == ["Kind"]


def test_add_selbstbeziehung_verboten(welt) -> None:
    from diakronos_app.api.beziehungen import add_beziehung

    sess = welt
    set_user(ADMIN)
    with pytest.raises(ValidationError) as fehler:
        add_beziehung(ANNA, ANNA, "Sonstiges")
    assert "selbst" in str(fehler.value)
    assert _zeilen(sess, ANNA) == []


def test_add_unbekannte_art_und_unbekannte_person(welt) -> None:
    from diakronos_app.api.beziehungen import add_beziehung

    sess = welt
    set_user(ADMIN)
    with pytest.raises(ValidationError) as fehler:
        add_beziehung(ANNA, BRUNO, "Freund")  # nicht in BEZIEHUNGSARTEN
    assert "Unbekannte Beziehungsart" in str(fehler.value)
    with pytest.raises(DoesNotExistError):
        add_beziehung(ANNA, "M-gibt-es-nicht@x.org", "Kind")
    with pytest.raises(ValidationError):
        add_beziehung(ANNA, "", "Kind")
    assert _zeilen(sess, ANNA) == []


# ── Rechte ──────────────────────────────────────────────────────────────────


def test_nur_verwaltung_darf_alle_drei_endpunkte(welt) -> None:
    """Normales Mitglied: fremdes Profil -> 403 auf allen drei Endpunkten.

    Eigenes Profil (Manuel 17.11.2026): nur Personen desselben Haushalts
    (gleiche Anschrift) — ohne Anschrift also niemand.
    """
    from diakronos_app.api.beziehungen import (
        add_beziehung,
        get_beziehungen_auswahl,
        remove_beziehung,
    )

    sess = welt
    set_user(ADMIN)
    antwort = add_beziehung(ANNA, BRUNO, "Kind")
    zeile = antwort["beziehung"]["name"]

    set_user(MITGLIED)
    eigenes = "M-lena@x.org"
    # Fremdes Profil: alle drei Endpunkte verweigert.
    with pytest.raises(PermissionError):
        get_beziehungen_auswahl(ANNA)
    with pytest.raises(PermissionError):
        add_beziehung(ANNA, CLARA, "Ehepartner")
    with pytest.raises(PermissionError):
        remove_beziehung(ANNA, zeile)
    # Eigenes Profil (Manuel 17.11.): Auswahl nur Haushalt (hier: keine
    # Anschrift -> leer), Eintragen ausserhalb des Haushalts verweigert.
    assert get_beziehungen_auswahl(eigenes)["data"] == []
    with pytest.raises(PermissionError):
        add_beziehung(eigenes, CLARA, "Ehepartner")
    # Nichts geschrieben, nichts entfernt.
    assert len(_paar(sess, ANNA, BRUNO)) == 1
    assert _paar(sess, eigenes, CLARA) == []
    assert _paar(sess, CLARA, eigenes) == []


def test_nur_verwaltung_auch_mit_eigenem_schreibrecht(welt) -> None:
    """Selbst `can_edit` am eigenen Profil oeffnet die Endpunkte nicht.

    Die Schranke ist die Rolle, nicht das Zeilenrecht — ein Mitglied mit
    Schreibrecht an der EIGENEN Zeile duerfte sonst Zeilen bei anderen
    anlegen (genau der Weg aus dem Review).
    """
    from diakronos_app.api.beziehungen import add_beziehung
    from diakronos_app.frappe_compat import permissions
    from diakronos_app.models.core import HasRole

    sess = welt
    eigenes = "M-lena@x.org"
    # Konto verknuepfen + Schreibrecht an der eigenen Zeile.
    sess.query(Mitglied).filter_by(name=eigenes).update({"user": MITGLIED})
    sess.commit()
    set_user(MITGLIED)
    assert permissions.mitglied_permissions(eigenes)["can_edit"] is True
    assert permissions._has_admin_role() is False
    with pytest.raises(PermissionError):
        add_beziehung(eigenes, ANNA, "Ehepartner")
    assert _paar(sess, eigenes, ANNA) == []
    assert sess is not None and HasRole is not None


def test_after_umlaut_arten_sind_erlaubt(welt) -> None:
    """Die Liste der Arten ist die des Altcodes (Select-Feld)."""
    from diakronos_app.api.beziehungen import BEZIEHUNGSARTEN, INVERS

    assert set(BEZIEHUNGSARTEN) == {"Elternteil", "Kind", "Ehepartner",
                                    "Geschwister", "Sonstiges"}
    assert INVERS["Kind"] == "Elternteil"
    assert INVERS["Elternteil"] == "Kind"
    assert INVERS["Ehepartner"] == "Ehepartner"
    for art in BEZIEHUNGSARTEN:
        assert INVERS[INVERS[art]] == art


# ── Entfernen: beide Richtungen, Rueckgaengig-Angaben, Audit ────────────────


def test_remove_raeumt_beide_richtungen(welt) -> None:
    from diakronos_app.api.beziehungen import add_beziehung, remove_beziehung

    sess = welt
    set_user(ADMIN)
    antwort = add_beziehung(ANNA, BRUNO, "Kind")
    zeile = antwort["beziehung"]["name"]

    weg = remove_beziehung(ANNA, zeile)
    assert weg["success"] is True
    assert [e["beziehungstyp"] for e in weg["entfernt"]] == ["Kind", "Elternteil"]
    assert weg["wiederherstellbar"] == {"beziehung_zu": BRUNO, "beziehungsart": "Kind"}
    assert _paar(sess, ANNA, BRUNO) == []
    assert _paar(sess, BRUNO, ANNA) == []

    eintrag = [z for z in _audit_zeilen(sess) if "Beziehung entfernt" in z["begruendung"]]
    assert len(eintrag) == 1
    assert "samt Gegenrichtung" in eintrag[0]["begruendung"]

    # Wiederherstellen = derselbe Weg wie beim Eintragen.
    add_beziehung(ANNA, BRUNO, weg["wiederherstellbar"]["beziehungsart"])
    assert len(_paar(sess, ANNA, BRUNO)) == 1
    assert len(_paar(sess, BRUNO, ANNA)) == 1


def test_remove_raeumt_auch_die_eigenhaendige_gegenangabe(welt) -> None:
    """Review 10.11.: symmetrisch — die Gegenzeile geht IMMER mit.

    Auch wenn die andere Person sie SELBST eingetragen hat (keine
    Spiegel-Marke): eine halbe Beziehung waere keine Aussage mehr. Der Test
    ersetzt `test_remove_laesst_fremde_eigene_angabe_stehen` (die alte Regel
    ist mit dem Review aufgehoben, Regel 19: begruendet umgebaut, nicht
    abgeschaltet).
    """
    from diakronos_app.api.beziehungen import remove_beziehung

    sess = welt
    # Bruno traegt „Elternteil zu Anna" SELBST ein (keine Spiegel-Marke) und
    # Anna hat die Gegenrichtung als Spiegel-Zeile (so legt sie auch
    # `add_beziehung` an).
    sess.add_all([
        MitgliedBeziehung(
            name="MBZ-bruno-eigen", parent=BRUNO, parenttype="Mitglied",
            parentfield="beziehungen", beziehung_zu=ANNA, beziehungstyp="Elternteil",
            ist_spiegel=0, docstatus=0, idx=1,
        ),
        MitgliedBeziehung(
            name="MBZ-anna-spiegel", parent=ANNA, parenttype="Mitglied",
            parentfield="beziehungen", beziehung_zu=BRUNO, beziehungstyp="Kind",
            ist_spiegel=1, docstatus=0, idx=1,
        ),
    ])
    sess.commit()
    set_user(ADMIN)

    weg = remove_beziehung(ANNA, "MBZ-anna-spiegel")
    # BEIDE Zeilen gehen: Annas Spiegel-Zeile und Brunos eigene Angabe.
    assert sorted(e["name"] for e in weg["entfernt"]) == [
        "MBZ-anna-spiegel", "MBZ-bruno-eigen",
    ]
    assert _paar(sess, ANNA, BRUNO) == []
    assert _paar(sess, BRUNO, ANNA) == []
    # Rueckgaengig ist anlegbar — und legt wieder beide Richtungen an.
    from diakronos_app.api.beziehungen import add_beziehung

    add_beziehung(ANNA, BRUNO, weg["wiederherstellbar"]["beziehungsart"])
    assert len(_paar(sess, ANNA, BRUNO)) == 1
    assert len(_paar(sess, BRUNO, ANNA)) == 1


def test_remove_unbekannte_zeile(welt) -> None:
    from diakronos_app.api.beziehungen import add_beziehung, remove_beziehung

    sess = welt
    set_user(ADMIN)
    with pytest.raises(DoesNotExistError):
        remove_beziehung(ANNA, "gibt-es-nicht")
    # Eine Zeile einer ANDEREN Person ist unter meiner Kennung nicht auffindbar.
    antwort = add_beziehung(ANNA, BRUNO, "Kind")
    with pytest.raises(DoesNotExistError):
        remove_beziehung(CLARA, antwort["beziehung"]["name"])


# ── Auswahlliste ────────────────────────────────────────────────────────────


def test_auswahl_ohne_selbst_und_ohne_email_treffer(welt) -> None:
    from diakronos_app.api.beziehungen import add_beziehung, get_beziehungen_auswahl

    sess = welt
    set_user(ADMIN)
    daten = get_beziehungen_auswahl(ANNA)["data"]
    kennungen = [z["mitglied"] for z in daten]
    assert ANNA not in kennungen, "die eigene Person ist keine Auswahl"
    assert BRUNO in kennungen
    assert all(set(z) == {"mitglied", "name", "in_beziehung"} for z in daten)

    add_beziehung(ANNA, BRUNO, "Kind")
    daten = get_beziehungen_auswahl(ANNA)["data"]
    bruno = next(z for z in daten if z["mitglied"] == BRUNO)
    assert bruno["in_beziehung"] is True

    # Suche in Vor-/Nachname (umlautgefaltet), NICHT in der E-Mail.
    assert [z["mitglied"] for z in get_beziehungen_auswahl(ANNA, "bruno")["data"]] == [BRUNO]
    assert get_beziehungen_auswahl(ANNA, "bruno@x.org")["data"] == []
    assert sess is not None


def test_auswahl_ohne_verwaltung_verweigert(welt) -> None:
    """Lesen am FREMDEN Profil verlangt Verwaltungsrecht."""
    from diakronos_app.api.beziehungen import get_beziehungen_auswahl

    set_user("niemand@x.org")
    with pytest.raises(PermissionError):
        get_beziehungen_auswahl(ANNA)
    # Angemeldet, aber ohne Rolle: ebenfalls verweigert.
    set_user(MITGLIED)
    with pytest.raises(PermissionError):
        get_beziehungen_auswahl(ANNA)


# ── Detailseite liefert die Zeilen wirklich mit ─────────────────────────────


def test_detail_enthaelt_die_beziehungen(welt) -> None:
    """Review 10.11.: `get_mitglied_detail` muss `beziehungen` mitliefern.

    `Document.as_dict()` gibt nur die SPALTEN zurueck — ohne den Nachtrag war
    der Reiter immer leer, obwohl Zeilen in der Datenbank standen (so im
    Browser belegt). Der Test haelt den Lesepfad der Oberflaeche fest.
    """
    from diakronos_app.api.beziehungen import add_beziehung
    from diakronos_app.api.mitglieder import get_mitglied_detail

    sess = welt
    set_user(ADMIN)
    add_beziehung(ANNA, BRUNO, "Kind")

    daten = get_mitglied_detail(ANNA)["data"]
    zeilen = daten.get("beziehungen") or []
    assert len(zeilen) == 1, "die Kindtabelle steht in der Detailantwort"
    assert zeilen[0]["beziehung_zu"] == BRUNO
    assert zeilen[0]["beziehungstyp"] == "Kind"
    # Der Anzeigename wird angereichert (die SPA zeigt ihn direkt).
    assert zeilen[0]["beziehung_zu_name"] == "Bruno Beispiel"
    # Die Gegenrichtung steht bei der anderen Person, nicht hier.
    gegen = get_mitglied_detail(BRUNO)["data"].get("beziehungen") or []
    assert [z["beziehungstyp"] for z in gegen] == ["Elternteil"]
    assert sess is not None


# ── Selbstpflege im Haushalt (Manuel 17.11.2026) ────────────────────────────


def _anschrift(sess, mitglied: str, strasse="Hauptstraße", nummer="5",
               plz="74072", ort="Heilbronn") -> None:
    sess.query(Mitglied).filter_by(name=mitglied).update(
        {"straße": strasse, "nummer": nummer, "postleitzahl": plz, "wohnort": ort})
    sess.commit()


def test_haushalt_selbst_eintragen_und_entfernen(welt) -> None:
    """Gleiche Anschrift (normalisiert): eintragen, Auswahl, entfernen am eigenen Profil."""
    from diakronos_app.api.beziehungen import (
        add_beziehung,
        get_beziehungen_auswahl,
        remove_beziehung,
    )

    sess = welt
    eigenes = "M-lena@x.org"
    _anschrift(sess, eigenes)
    _anschrift(sess, ANNA, strasse="hauptstr.", nummer=" 5 ", ort="HEILBRONN")
    _anschrift(sess, BRUNO, nummer="7")  # Nachbarhaus

    set_user(MITGLIED)
    auswahl = [z["mitglied"] for z in get_beziehungen_auswahl(eigenes)["data"]]
    assert auswahl == [ANNA], "nur der eigene Haushalt steht zur Auswahl"

    antwort = add_beziehung(eigenes, ANNA, "Ehepartner")
    assert len(_paar(sess, eigenes, ANNA)) == 1
    assert len(_paar(sess, ANNA, eigenes)) == 1
    with pytest.raises(PermissionError):
        add_beziehung(eigenes, BRUNO, "Geschwister")
    assert _paar(sess, eigenes, BRUNO) == []

    # Entfernen am eigenen Profil — auch nach einem Umzug.
    _anschrift(sess, ANNA, strasse="Neue Gasse")
    remove_beziehung(eigenes, antwort["beziehung"]["name"])
    assert _paar(sess, eigenes, ANNA) == [] and _paar(sess, ANNA, eigenes) == []


def test_haushalt_braucht_vollstaendige_anschrift(welt) -> None:
    from diakronos_app import rechte
    from diakronos_app.api.beziehungen import add_beziehung

    sess = welt
    eigenes = "M-lena@x.org"
    _anschrift(sess, eigenes, nummer="")
    _anschrift(sess, ANNA, nummer="")
    assert rechte.gleicher_haushalt(eigenes, ANNA) is False
    set_user(MITGLIED)
    with pytest.raises(PermissionError):
        add_beziehung(eigenes, ANNA, "Ehepartner")
    assert _paar(sess, eigenes, ANNA) == []


def test_haushalt_gilt_nicht_fuer_fremde_profile(welt) -> None:
    """Wohnt das Mitglied mit Anna UND Bruno zusammen, darf es trotzdem nicht
    an Annas Profil eine Beziehung zu Bruno eintragen."""
    from diakronos_app import rechte
    from diakronos_app.api.beziehungen import add_beziehung

    sess = welt
    for m in ("M-lena@x.org", ANNA, BRUNO):
        _anschrift(sess, m)
    set_user(MITGLIED)
    with pytest.raises(PermissionError):
        add_beziehung(ANNA, BRUNO, "Ehepartner")
    assert _paar(sess, ANNA, BRUNO) == []
    assert rechte.darf_beziehung(MITGLIED, "anlegen", ANNA, BRUNO).grund == "fremdes_profil"
    assert rechte.darf_beziehung(None, "lesen", ANNA).grund == "nicht_angemeldet"
    assert rechte.darf_beziehung(ADMIN, "anlegen", ANNA, BRUNO).grund == "verwaltung"


def test_detail_flag_beziehungen_pflegen(welt) -> None:
    """Knopf-Flag = Serverrecht: eigenes Profil ja, fremdes nein, Verwaltung ja."""
    from diakronos_app.api.mitglieder import get_mitglied_detail

    set_user(MITGLIED)
    eigen = get_mitglied_detail("M-lena@x.org")["permissions"]
    assert eigen["beziehungen_pflegen"] is True and eigen["beziehungen_alle"] is False
    set_user(ADMIN)
    fremd = get_mitglied_detail(ANNA)["permissions"]
    assert fremd["beziehungen_pflegen"] is True and fremd["beziehungen_alle"] is True
    set_user(MITGLIED)
    try:
        anna = get_mitglied_detail(ANNA)["permissions"]
    except Exception:  # noqa: BLE001 — Sichtbarkeit darf das Profil ganz sperren
        return
    assert anna["beziehungen_pflegen"] is False
