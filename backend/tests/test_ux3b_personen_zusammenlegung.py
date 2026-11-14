"""UX3b — Personen = Mitglieder + Adressbuch: die Server-Verträge der Ansicht.

Die Karte legt „Personen“ für alle Rollen zusammen. Welche Felder eine Zeile
tragen darf, entscheidet der SERVER — die Ansicht wählt nur die QUELLE:

  • Mitgliederadministrator → `get_mitglieder_liste` (persönliche Daten nur auf
    Anforderung),
  • alle anderen            → `get_adressbuch` (B2: `adressbuch_sichtbarkeit`).

Diese Tests nageln genau das fest, damit die Zusammenlegung kein Datenzuwachs
wird:

  1. Der Nicht-Admin bekommt aus BEIDEN Wegen dieselben Felder — und aus dem
     Adressbuch kein Feld mehr als vorher (Schlüssel-Vertrag der Zeile).
  2. Eine nicht freigegebene E-Mail steht auch im Adressbuch NICHT im
     Antwortkörper (kein `null`-Trick, kein Zweitfeld mit dem Wert).
  3. Status/Gruppen (Verwaltungswissen) liefert das Adressbuch nicht — die
     Adressbuch-Sicht darf sie also gar nicht erst anzeigen können.
  4. Die Auswahl der Quelle je Rolle hängt an EINEM Wahrheitswert (`isAdmin`),
     den derselbe Rollenstand speist wie die Rechteprüfung.
"""

from __future__ import annotations

import json

import pytest

from tests.test_permissions import hierarchie  # noqa: F401 — Fixture

SICHTBAR = "M-verantw-a"

# Felder, die `get_adressbuch` je Zeile ausliefert (Altcode-Vertrag). Die
# Ansicht baut ihre Zeile AUSSCHLIESSLICH aus diesen Schlüsseln.
ADRESSBUCH_SCHLUESSEL = {
    "name", "vorname", "nachname", "foto",
    "email", "telefonnummer", "postleitzahl", "wohnort", "geburtstag",
    # R-9: „Daten anfragen“ moeglich (Schalter der Person, keine Werte)
    "daten_anfragbar",
}


@pytest.fixture()
def sess(patched_db):
    """Session der Test-DB — die `hierarchie`-Fixture legt ihre Zeilen hier ab."""
    s = patched_db()
    yield s
    s.close()


def _set_user(user: str) -> None:
    from diakronos_app.frappe_compat.session import set_user

    set_user(user)


def _sichtbarkeit_setzen(sess, mitglied: str, **schalter) -> None:
    from diakronos_app.models.diakonos import Mitglied

    blob = {
        "email": schalter.get("email", True),
        "telefonnummer": schalter.get("telefonnummer", True),
        "adresse": schalter.get("adresse", False),
        "geburtstag": schalter.get("geburtstag", False),
    }
    sess.get(Mitglied, mitglied).adressbuch_sichtbarkeit = json.dumps(blob)
    sess.commit()


def _adressbuch(client):
    r = client.get("/api/method/mitglieder.get_adressbuch")
    assert r.status_code == 200, r.text
    return r.json()["message"]["data"]


def _zeile(client, mitglied: str) -> dict:
    return next(z for z in _adressbuch(client) if z["name"] == mitglied)


# ── 1) Schlüssel-Vertrag der Zeile ──────────────────────────────────────────

def test_adressbuch_zeile_hat_genau_die_bekannten_schluessel(client, hierarchie, sess):  # noqa: F811
    """Die Adressbuch-Sicht baut ihre Zeile aus diesen Schlüsseln. Kommt ein
    Feld hinzu, ist das ein Datenzuwachs — dieser Test hält ihn an."""
    _set_user("mitglied-a@example.org")
    zeilen = _adressbuch(client)
    assert zeilen, "das Adressbuch liefert mindestens die eigene Zeile"
    for zeile in zeilen:
        assert set(zeile) == ADRESSBUCH_SCHLUESSEL, (
            f"Zeile {zeile.get('name')!r} trägt andere Schlüssel: "
            f"{sorted(set(zeile) - ADRESSBUCH_SCHLUESSEL)} zu viel, "
            f"{sorted(ADRESSBUCH_SCHLUESSEL - set(zeile))} zu wenig"
        )
    # Kein Verwaltungswissen (Status, Gruppen, Notiz) im Adressbuch.
    for verboten in ("status", "gruppen", "notiz", "adressbuch_sichtbarkeit",
                     "austritt_datum", "ancestor_path"):
        assert all(verboten not in z for z in zeilen), (
            f"{verboten!r} gehört nicht in die Adressbuch-Sicht"
        )


# ── 2) Nicht freigegebene Felder stehen NICHT im Körper ─────────────────────

def test_nicht_freigegebene_email_ist_nicht_im_koerper(client, hierarchie, sess):  # noqa: F811
    """B2 fail-closed: `email=False` heißt `None` — und nirgends ein Zweitfeld
    mit dem Wert (die Ansicht kann ihn also nicht versehentlich zeigen)."""
    _sichtbarkeit_setzen(sess, SICHTBAR, email=False, telefonnummer=False,
                         adresse=False, geburtstag=False)
    _set_user("mitglied-a@example.org")

    zeile = _zeile(client, SICHTBAR)
    assert zeile["email"] is None
    assert zeile["telefonnummer"] is None
    assert zeile["wohnort"] is None
    assert zeile["postleitzahl"] is None
    assert zeile["geburtstag"] is None
    # Namen sind kein Adressbuch-Feld — die Person bleibt erkennbar.
    assert zeile["vorname"] == "Vera"

    # Nirgends in der Antwort steht die Adresse als Wert.
    roh = json.dumps(_adressbuch(client), ensure_ascii=False)
    assert "verantw-a@example.org" not in roh, "die verborgene E-Mail leckt"
    assert "0170-2220002" not in roh, "die verborgene Telefonnummer leckt"


# ── 3) Freigabe genau eines Feldes bleibt genau eines ───────────────────────

def test_nur_freigegebene_felder_kommen_an(client, hierarchie, sess):  # noqa: F811
    """Gibt B nur die E-Mail frei, sieht A genau die E-Mail — Telefon und
    Adresse bleiben leer. Die Ansicht zeigt daraus „E-Mail verborgen“ bzw. „–“."""
    _sichtbarkeit_setzen(sess, SICHTBAR, email=True, telefonnummer=False,
                         adresse=False, geburtstag=False)
    _set_user("mitglied-a@example.org")

    zeile = _zeile(client, SICHTBAR)
    assert zeile["email"] == "verantw-a@example.org"
    assert zeile["telefonnummer"] is None
    assert zeile["wohnort"] is None


# ── 4) Die Ansicht braucht nur den Rollenstand, keine zweite Regel ──────────

def test_quellenwahl_braucht_nur_den_rollenstand(client, hierarchie, sess):  # noqa: F811
    """Die Ansicht entscheidet „Mitgliederliste oder Adressbuch“ anhand von
    `is_admin` aus demselben Boot-Objekt, das der Server prüft. Dieser Test
    hält fest, dass BEIDE Wege für denselben Nutzer erreichbar sind (kein
    403-Rätsel in der Oberfläche) und dass der Nicht-Admin-Weg keine
    Verwaltungsfelder trägt — mehr braucht die Ansicht nicht zu wissen."""
    _set_user("mitglied-a@example.org")

    # Nicht-Admin: Adressbuch antwortet (200) und trägt keine Verwaltungsfelder.
    zeilen = _adressbuch(client)
    assert zeilen
    assert all("status" not in z and "gruppen" not in z for z in zeilen)

    # Nicht-Admin: die Mitgliederliste antwortet ebenfalls — dort schneidet die
    # B2-Maskierung die Adressbuch-Felder nach der Freigabe ab. Die Ansicht
    # darf daraus nichts übernehmen, was der Server verweigert hat.
    r = client.get("/api/method/mitglieder.get_mitglieder_liste", params={"limit": 50})
    assert r.status_code == 200, r.text
    for zeile in r.json()["message"]["data"]:
        if zeile.get("name") == SICHTBAR:
            assert zeile.get("telefonnummer") is None
            assert zeile.get("wohnort") is None
            assert zeile.get("geburtstag") is None
