"""N3/N4-Reste: Normalisierung muss auch den Altbestand erfassen."""
import pytest


@pytest.mark.parametrize("ziel", ["mitglied", "user_email", "user_name"])
def test_email_dublette_altbestand(client, seed_mitglieder, monkeypatch, ziel):
    from diakronos_app.api import mitglieder
    from diakronos_app.models.core import User
    from diakronos_app.models.diakonos import Mitglied

    monkeypatch.setattr(mitglieder, "_is_admin", lambda: True)
    sess = seed_mitglieder
    if ziel == "mitglied":
        sess.get(Mitglied, "M-0001").email = "  ANNA@Example.ORG "
    else:
        sess.add(User(name="  ANNA@Example.ORG " if ziel == "user_name" else "konto-alt",
                      email="  ANNA@Example.ORG " if ziel == "user_email" else None,
                      full_name="Anna Alt", enabled=True))
        sess.get(Mitglied, "M-0001").email = None
    sess.commit()
    antwort = client.post("/api/method/mitglieder.pruefe_mitglied_dublette",
                          json={"email": "anna@example.org"})
    assert antwort.status_code == 200, antwort.text
    assert antwort.json()["message"]["dublette"]["grund"] == "email"
    antwort = client.post("/api/method/mitglieder.create_mitglied", json={
        "vorname": "Andere", "nachname": "Person", "email": "anna@example.org",
        "create_user": False,
    })
    assert antwort.status_code == 417, antwort.text
    # SEC-b (Fachentscheidung 2026-10-19, K1): Die Meldung nennt jetzt die
    # Person, zu der die Adresse gehoert — statt der frueheren pauschalen
    # Abweisung.
    assert "bereits zu" in antwort.text


def test_verlaengern_normiert_iso(monkeypatch):
    from diakronos_app.api import registrierungslink_api as api
    from types import SimpleNamespace

    gespeichert = {}
    monkeypatch.setattr(api, "require_admin", lambda: None)
    monkeypatch.setattr(api, "get_doc", lambda *args: SimpleNamespace(name="RL-1"))

    class Fertig(Exception):
        pass

    def update(doctype, name, werte):
        gespeichert.update(werte)
        raise Fertig()

    monkeypatch.setattr(api, "_update_doc", update)
    with pytest.raises(Fertig):
        api.verlaengern_link("RL-1", "20261231")
    assert gespeichert["gueltig_bis"] == "2026-12-31"
