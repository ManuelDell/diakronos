"""R-10: Rollen-Erklaerungen stehen neben dem Kern und decken alles ab."""

from diakronos_app.rechte import erklaerung, kern


def test_jede_systemrolle_und_jedes_modul_ist_erklaert():
    assert set(kern.SYSTEMROLLEN.values()) <= set(erklaerung.SYSTEMROLLEN)
    assert set(kern.ADMIN_ROLLEN) <= set(erklaerung.SYSTEMROLLEN)
    assert set(kern.MODULE) == set(erklaerung.MODULE)
    assert set(kern.STUFEN) == set(erklaerung.STUFEN)
    assert {"HV", "MV", "GL", "Mitglied"} == set(erklaerung.GRUPPENROLLEN)


def test_jede_erklaerung_hat_titel_kurz_und_listen():
    for eintrag in [*erklaerung.SYSTEMROLLEN.values(), *erklaerung.GRUPPENROLLEN.values(), erklaerung.GAST]:
        assert eintrag["titel"] and eintrag["kurz"]
        assert isinstance(eintrag["darf"], list) and isinstance(eintrag["darf_nicht"], list)


def test_endpunkt_liefert_alles(client):
    r = client.get("/api/method/diakronos_app.api.rechte.get_rollen_erklaerung")
    assert r.status_code == 200, r.text
    assert set(r.json()["message"]) == {"systemrollen", "gast", "gruppenrollen", "module", "stufen",
                                        "modul_titel", "stufen_titel", "systemrollen_reihenfolge",
                                        "einleitungen"}


def test_titel_reihenfolge_und_einleitungen_vollstaendig():
    """UI-R8: die Oberflaeche schreibt keine Titel fest — alles kommt von hier."""
    from diakronos_app.rechte import erklaerung as E, kern

    assert set(E.MODUL_TITEL) == set(kern.MODULE)
    assert set(E.STUFEN_TITEL) == set(E.STUFEN)
    assert set(E.SYSTEMROLLEN_REIHENFOLGE) == set(E.SYSTEMROLLEN)
    alles = E.alles()
    assert set(alles["einleitungen"]) == {"systemrollen", "gast", "gruppenrollen", "module", "stufen"}
    assert "öffentlich" not in " ".join(alles["einleitungen"].values()).lower()
