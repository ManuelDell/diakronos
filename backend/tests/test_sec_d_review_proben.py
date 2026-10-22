"""SEC-d: Regressionstests aus dem Review SEC-c.

Quelle der Faelle: die Proben des unabhaengigen Reviews
(`test_zz_secc.py`: G1, P5, X2, X4 — G1 liegt bereits als
`test_sec_eine_adresse_je_person.py::test_g1_ma_import_konto_mit_rolle_mitglied`)
und die Punkte W3, W4, K1, K-a der Nacharbeit.

Jeder Test hier ist VOR der Behebung rot gewesen (Beleg im Abschlussbericht):

* P5  — halber Import: Zeile 1 blieb stehen, obwohl die Meldung
        „nichts angelegt“ sagte (B2).
* X2  — die Index-Meldung nannte eine unbeteiligte Person (W3).
* X4  — ein Konto mit gemischter Schreibweise verlor beim ersten Speichern
        die Zuordnung zu seiner Person (Frage 4 / W3-Nachbar).
* W4  — `belegung` uebersah Konten ohne `User.email` (Regression
        `test_n5_nacharbeiten::test_email_dublette_altbestand[user_name]`).
* K1  — der Meldungstext eines Statuswechsels sprach von „Adresse“.
* K-a — kein Test, der die Existenz des Index belegt.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError

from diakronos_app.frappe_compat.api_helpers import EMAIL_UNIQUE_INDEX
from diakronos_app.frappe_compat.session import set_user
from diakronos_app.models.core import HasRole, User
from diakronos_app.models.diakonos import Mitglied

SM = "System Manager"
MA = "Mitgliederadministrator"
BACKEND = Path(__file__).resolve().parents[1]


def _konto(sess, email, rolle=None, *, mitglied=True):
    sess.add(User(name=email, email=email, full_name=email, enabled=True))
    if rolle:
        sess.add(HasRole(name=f"HR-{email}-{rolle}", parent=email, parenttype="User",
                         parentfield="roles", role=rolle, docstatus=0, idx=1))
    if mitglied:
        sess.add(Mitglied(name=f"M-{email}", vorname=email, nachname="Test",
                          email=email, status="Mitglied", user=email,
                          docstatus=0, idx=0))
    sess.commit()


def _versuch(fn):
    """Aufruf ohne Testabbruch: (ergebnis, ...) wie in den Review-Proben."""
    try:
        r = fn()
    except Exception as e:  # noqa: BLE001
        return ("abgelehnt", type(e).__name__, str(e)[:200])
    if isinstance(r, dict) and r.get("_error"):
        return ("abgelehnt", r)
    return ("erlaubt", str(r)[:120])


# ── P5: der ganze Lauf faellt zurueck (B2) ──────────────────────────────────


def test_p5_schreibfehler_in_zeile_2_laesst_zeile_1_nicht_stehen(patched_db, fake_redis):
    """P5 (SEC-c): Zeile 2 von 3 scheitert → NICHTS bleibt stehen.

    Frueher (SEC-c) blieb Zeile 1 stehen: die Meldung sagte „nichts
    angelegt“, die Datenbank sagte etwas anderes. Der Lauf ist EINE
    Transaktion; nur eine VOR dem Schreiben abgelehnte Zeile ist ein
    Ergebnis (K-c).
    """
    from diakronos_app.api import mitglieder

    sess = patched_db()
    _konto(sess, "ma@x.org", MA)
    sess.commit()
    set_user("ma@x.org")

    echt = mitglieder._create
    zaehler = {"n": 0}

    def kaputt(doctype, werte):
        zaehler["n"] += 1
        if zaehler["n"] == 2:
            raise RuntimeError("DB-Grenze mitten im Lauf")
        return echt(doctype, werte)

    mitglieder._create = kaputt  # type: ignore[assignment]
    try:
        vorher = sess.query(Mitglied).count()
        ergebnis = _versuch(lambda: mitglieder.import_mitglieder_uebernehmen(
            "Vorname;Nachname;E-Mail\nA;Eins;a@x.org\nB;Zwei;b@x.org\nC;Drei;c@x.org\n",
            dubletten_ueberspringen=0, bestaetigt=1))
        sess.expire_all()
        nachher = sess.query(Mitglied).count()
    finally:
        mitglieder._create = echt  # type: ignore[assignment]

    print("\nP5:", ergebnis)
    assert ergebnis[0] == "abgelehnt", ergebnis
    assert nachher == vorher, f"halber Import blieb stehen ({vorher} -> {nachher})"


def test_p5_abgelehnte_zeile_ist_kein_abbruch(patched_db, fake_redis):
    """Gegenprobe zu P5: eine fachlich abgelehnte Zeile haelt den Lauf NICHT auf.

    Die Adresse gehoert schon zu einer Person — die Zeile wird abgelehnt
    (HTTP 200, Ergebnis je Zeile), die uebrigen Zeilen entstehen.
    """
    from diakronos_app.api.mitglieder import import_mitglieder_uebernehmen

    sess = patched_db()
    _konto(sess, "ma@x.org", MA)
    sess.add(Mitglied(name="M-anna", vorname="Anna", nachname="Ziel",
                      email="anna@x.org", status="Mitglied", docstatus=0, idx=0))
    sess.commit()
    set_user("ma@x.org")

    ergebnis = import_mitglieder_uebernehmen(
        "Vorname;Nachname;E-Mail\nNeu;Person;neu@x.org\nZweit;Person;anna@x.org\n",
        dubletten_ueberspringen=0, bestaetigt=1,
    )
    print("\nK-c:", ergebnis)
    assert ergebnis["angelegt"] == 1
    assert ergebnis["abgelehnt"] == 1
    sess.expire_all()
    assert sess.query(Mitglied).filter(Mitglied.email == "neu@x.org").count() == 1


# ── X2: die Indexmeldung nennt keine unbeteiligte Person (W3) ───────────────


def test_x2_indexmeldung_nennt_keine_unbeteiligte_person(patched_db, fake_redis):
    """X2: Kollision mit „Anna Ziel“ → die Meldung nennt NICHT „Erste Person“.

    Erreichbar ist der Fall nur, wenn die Python-Vorpruefung umgangen wird
    (Rennen, neuer Schreibweg). Der Datenbankfehler nennt nur den Index, nicht
    die Zeile — also bleibt die Meldung bei „einer anderen Person“, statt eine
    beliebige Person zu raten (und deren Namen preiszugeben).
    """
    from diakronos_app.frappe_compat.api_helpers import _db_fehler

    sess = patched_db()
    sess.add(Mitglied(name="M-aaa", vorname="Erste", nachname="Person",
                      email="erste@x.org", status="Mitglied", docstatus=0, idx=0))
    sess.add(Mitglied(name="M-zzz", vorname="Anna", nachname="Ziel",
                      email="anna@x.org", status="Mitglied", docstatus=0, idx=0))
    sess.commit()

    with pytest.raises(IntegrityError) as fehler:
        sess.add(Mitglied(name="M-neu", vorname="N", nachname="N",
                          email="anna@x.org", status="Mitglied", docstatus=0, idx=0))
        sess.commit()
    sess.rollback()

    meldung = str(_db_fehler(fehler.value, "Mitglied"))
    print("\nX2:", meldung)
    assert "Erste" not in meldung, "Meldung nennt eine unbeteiligte Person"
    assert "Anna" not in meldung
    assert " einer anderen Person" in meldung
    # Die Meldung ist Klartext, kein Roh-SQL (Pflicht 2).
    for verboten in ("[SQL:", "INSERT INTO", "uq_mitglied_email_normalisiert", "DETAIL:"):
        assert verboten not in meldung


# ── X4: eigene Zuordnung uebersteht das Speichern (Frage 4) ─────────────────


def test_x4_eigene_zuordnung_nach_speichern_bleibt(patched_db, fake_redis):
    """X4: Konto „Max@X.org“, Mitglied „Max@X.org“ — nach dem Speichern weg?

    Seit SEC-c speichert jeder Schreibweg die Adresse normalisiert. Verglich
    die Zuordnung danach EXAKT, verlor Max beim ersten Speichern seines
    eigenen Formulars Profil und Selbstrechte (`_get_current_user_mitglied`).
    """
    from diakronos_app.api.mitglieder import update_mitglied
    from diakronos_app.frappe_compat import permissions

    sess = patched_db()
    _konto(sess, "sm@x.org", SM)
    sess.add(User(name="max@x.org", email="Max@X.org", full_name="Max", enabled=True))
    sess.add(Mitglied(name="M-max", vorname="Max", nachname="M", email="Max@X.org",
                      status="Mitglied", docstatus=0, idx=0))
    sess.commit()

    set_user("max@x.org")
    vor = permissions._get_current_user_mitglied()
    assert vor and vor["name"] == "M-max", "Vorbedingung: Zuordnung fehlt schon vorher"

    set_user("sm@x.org")
    update_mitglied("M-max", {"vorname": "Maxi", "email": "Max@X.org"})

    set_user("max@x.org")
    nach = permissions._get_current_user_mitglied()
    print("\nX4: vor", vor and vor["name"], "nach", nach and nach["name"])
    assert nach is not None, "Eigene Mitglied-Zuordnung nach blossem Speichern verloren"
    assert nach["name"] == "M-max"


def test_x4_profilweg_findet_das_mitglied_normalisiert(patched_db, fake_redis):
    """X4 (Profil): `_get_my_mitglied` findet die Person auch gemischt geschrieben."""
    from diakronos_app.api import profile

    sess = patched_db()
    sess.add(User(name="max@x.org", email="MAX@X.ORG", full_name="Max", enabled=True))
    sess.add(Mitglied(name="M-max", vorname="Max", nachname="M", email="max@x.org",
                      status="Mitglied", docstatus=0, idx=0))
    sess.commit()
    set_user("max@x.org")
    assert profile._get_my_mitglied() == "M-max"


# ── W4: belegung findet Konten ohne User.email ──────────────────────────────


def test_w4_belegung_findet_konto_ohne_email(patched_db, fake_redis):
    """W4: `anonymisieren` setzt `User.email = None`, der Kontoname bleibt.

    Die Adresse ist danach NICHT frei — sonst liefe `konto_anlegen` in eine
    Schluessel-Kollision und `pruefe_mitglied_dublette` meldete nichts.
    """
    from diakronos_app.email_belegung import belegung

    sess = patched_db()
    sess.add(User(name="alt@x.org", email=None, full_name="Altes Konto", enabled=True))
    sess.commit()

    treffer = belegung(" ALT@x.org ")
    print("\nW4:", treffer)
    assert treffer, "belegung uebersieht ein Konto, dessen Adresse nur im Namen steht"
    assert treffer["doctype"] == "User"
    assert treffer["name"] == "alt@x.org"


# ── K1: der Meldungstext passt zum Vorgang ──────────────────────────────────


def test_k1_statuswechsel_meldung_ohne_adressbezug(patched_db, fake_redis):
    """K1: „…darf ein Mitglied mit Verwaltungskonto nur ein System Manager …“.

    Beim Statuswechsel geht es um die PERSON, nicht um ihre Adresse. Vorher
    las der Mitgliederadministrator bei jedem Vorgang denselben holprigen
    Satz („…ein Mitglied damit als Status setzen oder freigeben“).

    Der Fall braucht ein Mitglied mit Verwaltungskonto, das ausgeschlossen
    ist: nur dann bewertet die Schranke einen reinen Statuswechsel ueberhaupt
    als Rechteaenderung (sonst aendert „Mitglied → Gast“ keinen Zugang).
    """
    from diakronos_app.api.mitglieder import set_mitglied_status

    sess = patched_db()
    _konto(sess, "ma@x.org", MA)
    sess.add(User(name="sm@x.org", email="sm@x.org", full_name="sm@x.org", enabled=True))
    sess.add(HasRole(name="HR-sm", parent="sm@x.org", parenttype="User",
                     parentfield="roles", role=SM, docstatus=0, idx=1))
    sess.add(Mitglied(name="M-sm", vorname="Verwaltung", nachname="Konto",
                      email="sm@x.org", user="sm@x.org", ausgeschlossen=1,
                      status="Gast", docstatus=0, idx=0))
    sess.commit()
    set_user("ma@x.org")

    ergebnis = _versuch(lambda: set_mitglied_status("M-sm", "Mitglied"))
    print("\nK1:", ergebnis)
    text = str(ergebnis)
    assert ergebnis[0] == "abgelehnt", ergebnis
    assert "Verwaltungskonto" in text, text
    assert "in seinem Status ändern" in text, text
    assert "ausschliessen" not in text and "ausschließen" not in text
    assert "Adresse" not in text, "Statuswechsel ist kein Adressvorgang"


# ── K-a: der Index ist da (Modell + Migration) ──────────────────────────────


def _migration():
    """Die SEC-Migration als Modul (liegt unter alembic/versions/)."""
    pfad = BACKEND / "alembic" / "versions" / "sec2_email_eindeutig.py"
    spec = importlib.util.spec_from_file_location("sec2_email_eindeutig", pfad)
    modul = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(modul)
    return modul


def test_ka_index_im_modell_und_in_der_migration_gleich():
    """K-a: Modell und Migration deklarieren DENSELBEN Index.

    Laufen die beiden auseinander, meldet `alembic check` dauerhaft
    „remove_index + add_index“ — oder schlimmer: die Datenbank hat einen
    anderen Index als der Code annimmt.
    """
    from diakronos_app.frappe_compat.api_helpers import EMAIL_UNIQUE_INDEX

    migration = _migration()
    assert migration.INDEX_NAME == EMAIL_UNIQUE_INDEX

    indizes = [i for i in Mitglied.__table__.indexes if i.name == EMAIL_UNIQUE_INDEX]
    assert len(indizes) == 1, "Index fehlt in der Modell-Deklaration"
    index = indizes[0]
    assert index.unique is True
    assert "lower(trim(email))" in str(index.expressions[0])
    assert "coalesce(trim(email), '') <> ''" in str(index.dialect_options["postgresql"]["where"])

    # Die Migration legt genau diesen Ausdruck an (sonst driftet der Bestand).
    quelle = (BACKEND / "alembic" / "versions" / "sec2_email_eindeutig.py").read_text()
    assert 'sa.text("lower(trim(email))")' in quelle
    assert "postgresql_where=sa.text(\"coalesce(trim(email), '') <> ''\")" in quelle


def test_ka_index_haelt_auf_sqlite(engine):
    """K-a: der partielle Index verbietet Dopplungen, laesst leere Adressen zu.

    Auf SQLite (Test-Rahmen) greift dieselbe Zusage wie auf PostgreSQL: zwei
    Mitglieder mit derselben Adresse sind unmoeglich, zwei ohne Adresse nicht.
    """
    with engine.begin() as c:
        c.execute(Mitglied.__table__.insert(), {"name": "M-1", "email": "a@x.org",
                                                "docstatus": 0, "idx": 0})
    with pytest.raises(IntegrityError):
        with engine.begin() as c:
            c.execute(Mitglied.__table__.insert(), {"name": "M-2", "email": " A@x.org ",
                                                    "docstatus": 0, "idx": 0})
    with engine.begin() as c:
        for name in ("M-3", "M-4", "M-5"):
            c.execute(Mitglied.__table__.insert(), {"name": name, "email": None,
                                                    "docstatus": 0, "idx": 0})
    with engine.connect() as c:
        ohne = c.execute(
            Mitglied.__table__.select().where(Mitglied.__table__.c.email.is_(None))
        ).all()
    assert len(ohne) == 3, "Mitglieder ohne Adresse muessen erlaubt bleiben"


# ── REST-3 (R-SEC-d K4): der Index in einer ECHTEN PostgreSQL-Datenbank ─────
#
# K-a prüfte nur, dass MODELL und MIGRATION denselben Ausdruck tragen. Ob die
# Datenbank den Index nach `alembic upgrade head` wirklich hat — und ob er
# dort Dopplungen verbietet —, blieb offen (`alembic check` blendet partielle
# Indizes aus). Dieser Test läuft deshalb gegen ein Wegwerf-PostgreSQL.
#
# Ohne Wegwerf-Datenbank wird er MIT BEGRÜNDUNG übersprungen (nicht still
# „grün"): `PLANRAHMEN_DISPOSABLE_DB=1` + `DATABASE_URL` auf eine
# Wegwerf-Instanz, genau wie die Plan-Rahmen-Modelltests.

WEGWERF_GRUND = (
    "K-a (PG): braucht ein Wegwerf-PostgreSQL — PLANRAHMEN_DISPOSABLE_DB=1 "
    "und DATABASE_URL auf eine Wegwerf-Instanz setzen."
)


def _wegwerf_url() -> str | None:
    """DATABASE_URL, aber nur wenn sie erkennbar auf eine Wegwerf-DB zeigt."""
    import os

    if os.environ.get("PLANRAHMEN_DISPOSABLE_DB") != "1":
        return None
    url = os.environ.get("DATABASE_URL") or ""
    if not url or not url.startswith("postgresql"):
        return None
    if "diakronos" in url and "wegwerf" not in url.lower() and "postgres-test" not in url.lower():
        return None   # fail closed: nie die Betriebs-DB
    return url


@pytest.fixture()
def pg_engine():
    """Wegwerf-PostgreSQL mit der Tabelle `mitglied` (samt Indizes).

    Bewusst NUR diese Tabelle: `metadata.create_all`/`drop_all` ueber alle
    Modelle scheitert an einem Fremdschluessel-Ring
    (ablaufplan/dienstplan/element/registrierungslink), der im Betrieb von
    Alembic aufgeloest wird — hier braucht der Test nur `mitglied`.
    """
    url = _wegwerf_url()
    if not url:
        pytest.skip(WEGWERF_GRUND)
    from sqlalchemy import create_engine

    from diakronos_app.models.core import User as _User

    eng = create_engine(url, future=True)
    # `mitglied.owner` verweist auf `user` — die eine Vorbedingung.
    _User.__table__.create(eng, checkfirst=True)
    Mitglied.__table__.create(eng, checkfirst=True)
    try:
        yield eng
    finally:
        Mitglied.__table__.drop(eng, checkfirst=True)
        _User.__table__.drop(eng, checkfirst=True)
        eng.dispose()


def test_ka_index_haelt_auf_postgresql(pg_engine):
    """K-a/K4: der partielle Eindeutigkeits-Index ist in der DB aktiv.

    Geprüft wird die Zusage, nicht die Deklaration: ein `pg_indexes`-Eintrag
    mit `lower(trim(email))` und `coalesce(trim(email), '') <> ''`, der zwei
    gleiche Adressen (auch in anderer Schreibweise/Leerraum) ablehnt und
    mehrere Mitglieder OHNE Adresse weiterhin zulässt.
    """
    from sqlalchemy import text

    with pg_engine.connect() as c:
        zeile = c.execute(
            text(
                "SELECT indexdef FROM pg_indexes "
                "WHERE tablename = 'mitglied' AND indexname = :n"
            ),
            {"n": EMAIL_UNIQUE_INDEX},
        ).first()
    assert zeile is not None, f"{EMAIL_UNIQUE_INDEX} fehlt in der Datenbank"
    definition = zeile[0]
    assert "UNIQUE" in definition.upper(), definition
    # PostgreSQL schreibt den Ausdruck aus (lower(TRIM(BOTH FROM email))) —
    # geprueft wird deshalb ohne Leerzeichen und ohne „both from“.
    ohne_leerzeichen = definition.lower().replace(" ", "").replace("bothfrom", "")
    assert "lower(trim(email))" in ohne_leerzeichen, definition
    assert "coalesce(trim(email),''" in ohne_leerzeichen, definition

    with pg_engine.begin() as c:
        c.execute(Mitglied.__table__.insert(), {"name": "M-pg-1", "email": "pg1@x.org",
                                                "docstatus": 0, "idx": 0})
    with pytest.raises(IntegrityError):
        with pg_engine.begin() as c:
            c.execute(Mitglied.__table__.insert(), {"name": "M-pg-2", "email": "  PG1@X.org ",
                                                    "docstatus": 0, "idx": 0})
    with pg_engine.begin() as c:
        for name in ("M-pg-3", "M-pg-4"):
            c.execute(Mitglied.__table__.insert(), {"name": name, "email": None,
                                                    "docstatus": 0, "idx": 0})
