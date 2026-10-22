"""SEC-c: EINE E-Mail-Adresse je Person — auch ueber die generischen Wege.

Quelle: Vorproben des Reviews (Opus), dort
`test_e_*` in `test_zz_secb.py`. Befund B1: die Fachentscheidung „jede Person
braucht eine eigene Adresse“ hielt nur auf den Fachendpunkten
(`create_mitglied`/`update_mitglied`). Alles andere verliess sich auf den
Datenbank-Index, und der vergleicht `lower(trim(email))` — PG/SQLite-`trim`
kennt weder Tab, Zeilenende noch NBSP und normalisiert kein NFKC. Damit
entstanden echte Dubletten: zwei Mitglieder mit „derselben“ Adresse, fuer die
Rechtepruefung mehrdeutig.

Dieser Test faehrt deshalb JEDEN Schreibweg gegen JEDE Variante und zaehlt
anschliessend die Mitglieder mit derselben (normalisierten) Adresse.
"""
from __future__ import annotations

import unicodedata

import pytest

from diakronos_app.frappe_compat.session import set_user
from diakronos_app.models.core import HasRole, User
from diakronos_app.models.diakonos import Mitglied

SM = "System Manager"
MA = "Mitgliederadministrator"

#: Dieselbe Adresse in allen Schreibweisen, die im Betrieb als Dublette
#: durchkamen (Tab, Zeilenende, NBSP, Vollbreite, unsichtbare Zeichen).
VARIANTEN = [
    "anna@x.org",
    "ANNA@x.org",
    " Anna@X.ORG ",
    "\tanna@x.org",
    "anna@x.org\n",
    "\u00a0anna@x.org",
    "ａｎｎａ@x.org",
    "anna@x.org\u200b",
    "an\u00adna@x.org",
]

#: Alle Wege, auf denen ein Mitglied entsteht oder seine Adresse wechselt.
WEGE = [
    "create_mitglied",
    "update_mitglied",
    "resource_post",
    "resource_put",
    "client_insert",
    "_create",
    "_update_doc",
    "db_set",
    "db_set_mitglied",
    "import_bestaetigt",
    "genehmige_anmeldung",
]


def _norm(email) -> str:
    """Pruefnormalisierung des Tests — absichtlich NUR Unicode."""
    text = unicodedata.normalize("NFKC", str(email or ""))
    for zeichen in ("\u200b", "\u200c", "\u200d", "\u2060", "\ufeff", "\u00ad"):
        text = text.replace(zeichen, "")
    return text.strip().lower()


def _anzahl_anna(sess) -> int:
    sess.expire_all()
    return sum(1 for m in sess.query(Mitglied).all() if _norm(m.email) == "anna@x.org")


def _konto(sess, email, rolle=None):
    sess.add(User(name=email, email=email, full_name=email, enabled=True))
    if rolle:
        sess.add(HasRole(name=f"HR-{email}-{rolle}", parent=email, parenttype="User",
                         parentfield="roles", role=rolle, docstatus=0, idx=1))
    sess.add(Mitglied(name=f"M-{email}", vorname=email, nachname="Test",
                      email=email, status="Mitglied", user=email,
                      ausgeschlossen=0, docstatus=0, idx=0))
    sess.commit()


def _basis(patched_db, wer="ma@x.org"):
    sess = patched_db()
    _konto(sess, "ma@x.org", MA)
    _konto(sess, "sm@x.org", SM)
    _konto(sess, "anna@x.org")
    sess.add(Mitglied(name="M-b", vorname="B", nachname="B", email="b@x.org",
                      status="Mitglied", docstatus=0, idx=0))
    sess.commit()
    set_user(wer)
    return sess


def _weg(name, wert, sess):
    if name == "create_mitglied":
        from diakronos_app.api.mitglieder import create_mitglied
        return lambda: create_mitglied("Zweit", "Person", email=wert)
    if name == "update_mitglied":
        from diakronos_app.api.mitglieder import update_mitglied
        return lambda: update_mitglied("M-b", {"email": wert})
    if name == "resource_post":
        from diakronos_app.frappe_compat import router
        return lambda: router._apply_resource_write(
            "Mitglied", None,
            {"name": "M-neu", "vorname": "Zweit", "nachname": "Person", "email": wert})
    if name == "resource_put":
        from diakronos_app.frappe_compat import router
        return lambda: router._apply_resource_write("Mitglied", "M-b", {"email": wert})
    if name == "client_insert":
        from diakronos_app.api.frappe_core import insert
        return lambda: insert(doc={"doctype": "Mitglied", "vorname": "Zweit",
                                   "nachname": "Person", "email": wert})
    if name == "_create":
        from diakronos_app.frappe_compat.api_helpers import _create
        return lambda: _create("Mitglied", {"vorname": "Zweit", "nachname": "Person",
                                            "email": wert})
    if name == "_update_doc":
        from diakronos_app.frappe_compat.api_helpers import _update_doc
        return lambda: _update_doc("Mitglied", "M-b", {"email": wert})
    if name == "db_set":
        from diakronos_app.frappe_compat.query import get_doc
        return lambda: get_doc("Mitglied", "M-b").db_set("email", wert)
    if name == "db_set_mitglied":
        # Weg wie `zugang.konto_anlegen`: geladenes Dokument, `db_set` mit
        # der Adresse — derselbe generische Weg mit einem Mitglied.
        from diakronos_app.frappe_compat.query import get_doc
        return lambda: get_doc("Mitglied", "M-b").db_set("email", wert)
    if name == "import_bestaetigt":
        from diakronos_app.api.mitglieder import import_mitglieder_uebernehmen
        # Zeilenende wuerde die CSV zerlegen — dort als Leerzeichen senden.
        zelle = wert.replace("\n", " ")
        text = f"Vorname;Nachname;E-Mail\nZweit;Person;{zelle}\n"
        return lambda: import_mitglieder_uebernehmen(
            text, dubletten_ueberspringen=0, bestaetigt=1)
    if name == "genehmige_anmeldung":
        from diakronos_app.models.diakonos import Anmeldung
        sess.add(Anmeldung(name="ANM-1", anmeldungstyp="Mitglied-Registrierung",
                           status="Offen", vorname="Zweit", nachname="Person",
                           email=wert, docstatus=0, idx=0))
        sess.commit()
        from diakronos_app.api.admin_hub import genehmige_anmeldung
        return lambda: genehmige_anmeldung("ANM-1", dublette_bestaetigt=1)
    raise AssertionError(name)


def _versuch(fn):
    try:
        ergebnis = fn()
    except Exception as exc:  # noqa: BLE001 — jeder Ausgang ist hier erlaubt
        return ("abgelehnt", type(exc).__name__, str(exc)[:200])
    if isinstance(ergebnis, dict) and ergebnis.get("_error"):
        return ("abgelehnt", ergebnis)
    status = getattr(ergebnis, "status_code", None)
    if status is not None and status >= 400:
        return ("abgelehnt", status)
    return ("erlaubt", str(ergebnis)[:120])


@pytest.mark.parametrize("variante", VARIANTEN, ids=[repr(v) for v in VARIANTEN])
@pytest.mark.parametrize("weg", WEGE)
def test_zweite_person_gleiche_adresse_abgewiesen(patched_db, fake_redis, weg, variante):
    """Jeder Weg weist eine zweite Person mit derselben Adresse ab."""
    sess = _basis(patched_db)
    ergebnis = _versuch(_weg(weg, variante, sess))
    anzahl = _anzahl_anna(sess)
    assert anzahl == 1, (
        f"{weg} {variante!r}: zweite Person mit derselben Adresse angelegt "
        f"({ergebnis!r})"
    )


@pytest.mark.parametrize("weg", ["create_mitglied", "client_insert", "genehmige_anmeldung"])
def test_system_manager_ebenso_abgewiesen(patched_db, fake_redis, weg):
    """Auch der System Manager legt keine zweite Person mit derselben Adresse an."""
    sess = _basis(patched_db, wer="sm@x.org")
    _versuch(_weg(weg, " ANNA@x.org", sess))
    assert _anzahl_anna(sess) == 1


@pytest.mark.parametrize("weg", WEGE)
def test_meldung_nennt_kein_sql(patched_db, fake_redis, weg):
    """W1: eine Dublette liefert eine fachliche Meldung, nie SQL oder Parameter."""
    sess = _basis(patched_db)
    ergebnis = _versuch(_weg(weg, "ANNA@x.org", sess))
    text = str(ergebnis)
    for verboten in ("INSERT INTO", "[SQL:", "SELECT ", "uq_mitglied_email_normalisiert",
                     "UNIQUE constraint", "TRIM(", "DETAIL:"):
        assert verboten not in text, f"{weg}: Roh-SQL in der Antwort ({text[:200]})"


def test_w1_indexfehler_wird_uebersetzt(patched_db, fake_redis, monkeypatch):
    """W1: auch der ROHE Indexfehler kommt als Klartext beim Client an.

    Fuer diesen Fall wird die Python-Vorpruefung der Schranke abgeschaltet —
    dann schlaegt only der Datenbank-Index zu (wie bei einer gleichzeitigen
    zweiten Anfrage). `frappe.client.insert` reichte `str(exc)` durch:
    `(sqlite3.IntegrityError) UNIQUE constraint failed … [SQL: INSERT INTO …`.
    """
    sess = _basis(patched_db)
    from diakronos_app.api.frappe_core import insert
    from diakronos_app.frappe_compat import api_helpers

    monkeypatch.setattr(api_helpers, "_normalisiere_mitglied_email",
                        lambda data, name=None: data)
    ergebnis = _versuch(lambda: insert(doc={"doctype": "Mitglied", "vorname": "Zweit",
                                            "nachname": "Person", "email": "ANNA@x.org"}))
    assert ergebnis[0] == "abgelehnt", ergebnis
    text = str(ergebnis)
    for verboten in ("INSERT INTO", "[SQL:", "uq_mitglied_email_normalisiert",
                     "UNIQUE constraint", "TRIM(", "DETAIL:"):
        assert verboten not in text, f"Roh-SQL in der Antwort ({text[:200]})"
    assert "E-Mail-Adresse gehört bereits" in text, text


@pytest.mark.parametrize("weg", WEGE)
def test_meldung_nennt_die_person(patched_db, fake_redis, weg):
    """Die Dubletten-Meldung nennt, WEM die Adresse schon gehoert."""
    sess = _basis(patched_db)
    # `/api/resource` antwortet wie in Frappe mit Status + `message` im Body;
    # den Text holt der Test deshalb direkt vom Rückgabewert des Wegs.
    try:
        antwort = _weg(weg, "ANNA@x.org", sess)()
        text = bytes(antwort.body).decode() if hasattr(antwort, "body") else str(antwort)
    except Exception as exc:  # noqa: BLE001 — die Meldung IST das Ergebnis
        text = str(exc)
    # Name des Bestandsmitglieds „anna@x.org“ ist „anna@x.org Test“.
    assert "anna@x.org" in text, f"{weg}: Meldung nennt die Person nicht ({text[:200]})"


def test_leere_adressen_bleiben_erlaubt(patched_db, fake_redis):
    """Ohne Adresse darf mehrfach angelegt werden (Adresse ist optional)."""
    _basis(patched_db)
    from diakronos_app.api.frappe_core import insert

    ausgaenge = [
        _versuch(lambda e=e, i=i: insert(doc={"doctype": "Mitglied", "vorname": "L",
                                              "nachname": str(i), "email": e}))[0]
        for i, e in enumerate([None, "", None, "", "  ", "\t"])
    ]
    assert ausgaenge == ["erlaubt"] * 6, ausgaenge


def test_platzhalter_adresse_gilt_als_leer(patched_db, fake_redis):
    """K-b: `-` (Platzhalter aus dem Betrieb) ist keine Adresse.

    Der Betrieb hat nachweislich ein Mitglied mit E-Mail „-“. Eine zweite
    Person mit „-“ wurde bisher als Dublette abgewiesen („gehoert bereits zu
    …“), obwohl beide gar keine Adresse haben. Geprueft wird nur beim
    Schreiben; bestehende Daten bleiben unangetastet.
    """
    sess = patched_db()
    _konto(sess, "ma@x.org", MA)
    sess.add(Mitglied(name="M-strich", vorname="Alt", nachname="Bestand",
                      email="-", status="Mitglied", docstatus=0, idx=0))
    sess.commit()
    set_user("ma@x.org")

    from diakronos_app.frappe_compat.api_helpers import _create

    ergebnis = _versuch(lambda: _create("Mitglied", {"vorname": "Zweit", "nachname": "Person",
                                                     "email": "-"}))
    assert ergebnis[0] == "erlaubt", ergebnis


def test_platzhalter_adresse_wird_als_leer_gespeichert(patched_db, fake_redis):
    """K-b: beim Schreiben wird der Platzhalter zu „keine Adresse“ (NULL)."""
    _basis(patched_db)
    from diakronos_app.frappe_compat.api_helpers import _create
    from diakronos_app.frappe_compat.query import get_value

    name = _create("Mitglied", {"vorname": "Zweit", "nachname": "Person", "email": " - "})
    assert get_value("Mitglied", name, "email") in (None, "")


@pytest.mark.parametrize("platzhalter", ["-", " – ", "--", "n/a", "keine"])
def test_platzhalter_varianten_sind_keine_adresse(patched_db, fake_redis, platzhalter):
    """Alle Platzhalter-Schreibweisen zaehlen als „keine Adresse“."""
    _basis(patched_db)
    from diakronos_app.frappe_compat.api_helpers import _create
    from diakronos_app.frappe_compat.query import get_value

    name = _create("Mitglied", {"vorname": "Zweit", "nachname": "Person",
                                "email": platzhalter})
    assert get_value("Mitglied", name, "email") in (None, ""), platzhalter


def test_eigene_adresse_neu_schreiben_erlaubt(patched_db, fake_redis):
    """Eigene Adresse anders geschrieben speichern bleibt erlaubt."""
    sess = _basis(patched_db)
    from diakronos_app.api.mitglieder import update_mitglied

    # M-anna@x.org haengt an einem KONTO „anna@x.org“. Dessen Adresse auf ein
    # FREIES zu setzen muss erlaubt bleiben (die eigene Adresse ist der eigene
    # Datensatz, keine fremde Belegung).
    ergebnis = _versuch(lambda: update_mitglied("M-anna@x.org", {"email": "anna.neu@x.org"}))
    assert ergebnis[0] == "erlaubt", ergebnis
    sess.expire_all()
    gespeichert = sess.query(Mitglied).filter(Mitglied.name == "M-anna@x.org").one().email
    assert gespeichert == "anna.neu@x.org", gespeichert


def test_gespeicherter_wert_ist_normalisiert(patched_db, fake_redis):
    """Was geschrieben wird, ist die normalisierte Adresse — sonst greift der Index nicht."""
    _basis(patched_db)
    from diakronos_app.frappe_compat.api_helpers import _create
    from diakronos_app.frappe_compat.query import get_value

    name = _create("Mitglied", {"vorname": "Zweit", "nachname": "Person",
                                "email": "  NEU@X.ORG "})
    assert get_value("Mitglied", name, "email") == "neu@x.org"


def test_unsichtbare_zeichen_werden_abgewiesen(patched_db, fake_redis):
    """Eine Adresse mit unsichtbarem Zeichen wird nicht still „repariert“."""
    _basis(patched_db)
    from diakronos_app.frappe_compat.api_helpers import _create

    ergebnis = _versuch(lambda: _create("Mitglied", {"vorname": "Zweit", "nachname": "Person",
                                                     "email": "klar@x.org\u200b"}))
    assert ergebnis[0] == "abgelehnt", ergebnis
    assert "unsichtbare" in str(ergebnis)


# ── K1: Meldungstext je Vorgang ─────────────────────────────────────────────


def test_k1_statusaenderung_nennt_nicht_ausschliessen(patched_db, fake_redis):
    """Ein Mitgliederadministrator aendert den Status — die Meldung passt dazu."""
    sess = patched_db()
    _konto(sess, "ma@x.org", MA)
    _konto(sess, "sm@x.org", SM)
    _konto(sess, "alt@x.org", SM)
    sess.query(Mitglied).filter(Mitglied.name == "M-alt@x.org").one().ausgeschlossen = 1
    sess.commit()
    set_user("ma@x.org")

    from diakronos_app.api.mitglieder import set_mitglied_status

    ergebnis = _versuch(lambda: set_mitglied_status("M-alt@x.org", "Gast"))
    assert "ausschliessen" not in str(ergebnis), ergebnis
    assert "ausschließen" not in str(ergebnis), ergebnis


def test_k1_ausschluss_bleibt_ausschluss(patched_db, fake_redis):
    """Gegenprobe: beim echten Ausschluss bleibt der Vorgang benannt."""
    sess = patched_db()
    _konto(sess, "ma@x.org", MA)
    _konto(sess, "sm@x.org", SM)
    set_user("ma@x.org")

    from diakronos_app.frappe_compat.api_helpers import _update_doc

    ergebnis = _versuch(lambda: _update_doc("Mitglied", "M-sm@x.org", {"ausgeschlossen": 1}))
    assert ergebnis[0] == "abgelehnt", ergebnis
    assert "ausschließ" in str(ergebnis) or "ausschliess" in str(ergebnis), ergebnis
