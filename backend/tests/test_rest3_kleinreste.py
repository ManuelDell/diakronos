"""REST-3 — Kleinreste aus dem SEC-d-Review (Befunde Klein 1–3).

Quelle: Opus-Review, Abschnitt „Klein":
  K1  `_import_abbruch` protokollierte `str(exc)` — bei einem Datenbankfehler
      standen damit rohes SQL und die Adresse im LOG.
  K2  Beim Index-Rennen hiess die Meldung „die Zeile liess sich nicht
      speichern" statt „Adresse gehört bereits zu einer anderen Person".
  K3  `_get_current_user_mitglied`: Vollscan bleibt (REST-3b, s. unten).

Jeder Test ist VOR der Behebung rot gewesen (Beleg im Abschlusskommentar).
"""
from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from diakronos_app.frappe_compat.exceptions import ValidationError
from diakronos_app.frappe_compat.session import set_user
from diakronos_app.models.core import User
from diakronos_app.models.diakonos import Mitglied

MA = "Mitgliederadministrator"


def _konto(sess, email, rolle=None):
    from diakronos_app.models.core import HasRole

    sess.add(User(name=email, email=email, full_name=email, enabled=True))
    if rolle:
        sess.add(HasRole(name=f"HR-{email}-{rolle}", parent=email, parenttype="User",
                         parentfield="roles", role=rolle, docstatus=0, idx=1))
    sess.commit()


# ── K1: kein Roh-SQL und keine Adresse im Log ───────────────────────────────

def test_k1_import_abbruch_loggt_kein_sql_und_keine_adresse(patched_db, fake_redis, capsys):
    """K1: Der Protokolleintrag nennt die Fehlerklasse, nicht den Treibertext.

    Ein Datenbankfehler traegt SQL, Parameter und die Adresse des Mitglieds.
    `_db_fehler` haelt es vor (nur Fehlerklasse) — `_import_abbruch` nicht.
    """
    from diakronos_app.api import mitglieder

    sess = patched_db()
    _konto(sess, "ma@x.org", MA)
    sess.commit()
    set_user("ma@x.org")

    fehler = IntegrityError(
        "INSERT INTO mitglied (email) VALUES (%(email)s)",
        {"email": "streng.geheim@x.org"},
        Exception("duplicate key value violates unique constraint "
                  "uq_mitglied_email_normalisiert DETAIL: Key (lower(trim(email)))"
                  "=(streng.geheim@x.org) already exists."),
    )

    capsys.readouterr()
    mitglieder._import_abbruch(3, fehler)
    log = capsys.readouterr().err

    print("\nK1-Log:", log.strip())
    assert "IntegrityError" in log, "Die Fehlerklasse fehlt im Log"
    assert "streng.geheim@x.org" not in log, "Adresse steht im Log"
    assert "INSERT INTO" not in log, "Rohes SQL steht im Log"
    assert "DETAIL:" not in log, "Treibertext steht im Log"
    assert "%(email)s" not in log, "Parameterplatzhalter steht im Log"


def test_k1_fachlicher_grund_bleibt_im_log_erkennbar(patched_db, fake_redis, capsys):
    """Gegenprobe: „Adresse vergeben“ ist kein Leck und bleibt erkennbar.

    Ohne diesen Hinweis findet der Betrieb die Ursache eines abgebrochenen
    Imports im Log nicht — der Klartext nennt aber keine Person und keine
    Adresse.
    """
    from diakronos_app.api import mitglieder

    sess = patched_db()
    _konto(sess, "ma@x.org", MA)
    sess.commit()
    set_user("ma@x.org")

    from diakronos_app.frappe_compat.api_helpers import _db_fehler

    fehler = _db_fehler(
        IntegrityError("INSERT", {}, Exception(
            'duplicate key value violates unique constraint "uq_mitglied_email_normalisiert"')),
        "Mitglied",
    )
    capsys.readouterr()
    mitglieder._import_abbruch(4, fehler)
    log = capsys.readouterr().err
    print("\nK1b-Log:", log.strip())
    assert "bereits vergeben" in log, "Der fachliche Grund fehlt im Log"
    assert "@" not in log, "Eine Adresse steht im Log"


# ── K2: Index-Rennen meldet den fachlichen Grund ────────────────────────────

def test_k2_import_abbruch_nennt_den_fachlichen_grund(patched_db, fake_redis, capsys):
    """K2: Ein Abbruchgrund in Klartext erreicht den Client unveraendert.

    Der Client sah beim Index-Rennen „die Zeile liess sich nicht speichern“,
    obwohl der Grund bekannt war („E-Mail-Adresse gehört bereits …“). Geprueft
    wird die Zusage: ein fachlicher Grund wird durchgereicht, ein roher
    Treibertext NICHT (der bleibt bei der allgemeinen Meldung).
    """
    from diakronos_app.api import mitglieder

    sess = patched_db()
    _konto(sess, "ma@x.org", MA)
    sess.commit()
    set_user("ma@x.org")

    echt = mitglieder._create
    from diakronos_app.frappe_compat.api_helpers import _db_fehler

    def kollision(doctype, werte):
        if werte.get("email") == "b@x.org":
            raise _db_fehler(
                IntegrityError("INSERT", {}, Exception(
                    'duplicate key value violates unique constraint '
                    '"uq_mitglied_email_normalisiert"')),
                doctype,
            )
        return echt(doctype, werte)

    mitglieder._create = kollision  # type: ignore[assignment]
    try:
        capsys.readouterr()
        ergebnis = mitglieder.import_mitglieder_uebernehmen(
            "Vorname;Nachname;E-Mail\nA;Eins;a@x.org\nB;Zwei;b@x.org\n",
            dubletten_ueberspringen=0, bestaetigt=1,
        )
    finally:
        mitglieder._create = echt  # type: ignore[assignment]
    log = capsys.readouterr().err

    print("\nK2-Ergebnis:", ergebnis)
    # Die Zeile wird abgelehnt und der Grund steht dabei — nicht die Sammelmeldung.
    zeile2 = [z for z in ergebnis["zeilen"] if z["zeile"] == 2][0]
    assert "gehört bereits zu einer anderen Person" in " ".join(zeile2["fehler"]), zeile2
    # Und das Log nennt die Fehlerklasse, nicht rohes SQL (K1).
    assert "IntegrityError" in log or "ValidationError" in log, log
    assert "INSERT INTO" not in log and "DETAIL:" not in log, log


def test_k2_roher_treibertext_bleibt_bei_der_allgemeinen_meldung(patched_db, fake_redis):
    """K2/Gegenprobe: ohne fachlichen Grund bleibt die allgemeine Meldung.

    `_ist_fachlicher_zeilengrund` darf NUR die eigene Klartext-Meldung von
    `_db_fehler` durchlassen — nie einen Treibertext mit SQL und Adresse.
    """
    from diakronos_app.api.mitglieder import _ist_fachlicher_zeilengrund

    assert _ist_fachlicher_zeilengrund(
        "Diese E-Mail-Adresse gehört bereits zu einer anderen Person. "
        "Jede Person braucht eine eigene Adresse."
    )
    assert not _ist_fachlicher_zeilengrund(
        'duplicate key value violates unique constraint "uq_mitglied_email_normalisiert" '
        "DETAIL: Key (lower(trim(email)))=(anna@x.org) already exists."
    )
    assert not _ist_fachlicher_zeilengrund(
        "INSERT INTO mitglied (email) VALUES (%(email)s)"
    )
    assert not _ist_fachlicher_zeilengrund("")


# ── K3: Zuordnung bleibt Vollscan (REST-3b) ─────────────────────────────────
#
# Die gezielte SQL-Vorauswahl aus REST-3 fand weniger als der Vollscan: SQL
# faltet Tab/Innenleerzeichen/Vollbreite nicht wie `normalisiere`. Bei
# ~25 Mitgliedern kostet der Vollscan nichts — er bleibt, die Faelle hier
# halten fest, dass jede Schreibweise weiter zugeordnet wird.

@pytest.mark.parametrize("gespeichert", [
    "\tmax@x.org",          # Tab am Rand
    "ma x@x.org",            # Innenleerzeichen
    "ｍａｘ@x.org",           # Vollbreite
    "MAX@X.ORG",
])
def test_k3_zuordnung_findet_jede_schreibweise(patched_db, fake_redis, altbestand_dublette,
                                               gespeichert):
    from diakronos_app.frappe_compat import permissions

    sess = patched_db()
    _konto(sess, "sm@x.org", MA)
    sess.add(User(name="max@x.org", email="max@x.org", full_name="Max", enabled=True))
    sess.add(Mitglied(name="M-max", vorname="Max", nachname="M", email=gespeichert,
                      status="Mitglied", docstatus=0, idx=0))
    sess.commit()

    set_user("max@x.org")
    treffer = permissions._get_current_user_mitglied()
    assert treffer is not None, f"Zuordnung verloren fuer {gespeichert!r}"
    assert treffer["name"] == "M-max"


def test_k3_tab_dublette_bleibt_mehrdeutig(patched_db, fake_redis, altbestand_dublette):
    """Altbestand „max@…“ + „\tmax@…“ → mehrdeutig, keine Zuordnung."""
    from diakronos_app.frappe_compat import permissions

    sess = patched_db()
    _konto(sess, "sm@x.org", MA)
    sess.add(User(name="max@x.org", email="max@x.org", full_name="Max", enabled=True))
    for name, mail in (("M-a", "max@x.org"), ("M-b", "\tmax@x.org")):
        sess.add(Mitglied(name=name, vorname="M", nachname=name, email=mail,
                          status="Mitglied", docstatus=0, idx=0))
    sess.commit()

    set_user("max@x.org")
    assert permissions._get_current_user_mitglied() is None


def test_k3_zuordnung_findet_umlaut_schreibweise(patched_db, fake_redis):
    """K3: Die gezielte Abfrage findet dieselbe Adresse in anderer Schreibweise.

    Konto „Max@X.org“ (gross, alt) — Mitglied „max@x.org“. Der Filter faltet
    Gross-/Kleinschreibung (und Umlaute) wie beim Schreiben; die Zuordnung
    bleibt damit erhalten (Regression zu X4).
    """
    from diakronos_app.frappe_compat import permissions

    sess = patched_db()
    _konto(sess, "sm@x.org", MA)
    sess.add(User(name="max@x.org", email="Max@X.org", full_name="M", enabled=True))
    sess.add(Mitglied(name="M-mue", vorname="Max", nachname="M",
                      email="max@x.org", status="Mitglied", docstatus=0, idx=0))
    sess.commit()

    set_user("max@x.org")
    treffer = permissions._get_current_user_mitglied()
    print("\nK3b:", treffer and treffer["name"])
    assert treffer is not None, "Gross-/Kleinschreibung nicht gefunden"
    assert treffer["name"] == "M-mue"


def test_k3_mehrdeutig_bleibt_verweigert(patched_db, fake_redis, altbestand_dublette):
    """K3: Zwei Mitglieder mit derselben Adresse → weiterhin keine Zuordnung."""
    from diakronos_app.frappe_compat import permissions

    sess = patched_db()
    _konto(sess, "sm@x.org", MA)
    sess.add(User(name="dopp@x.org", email="dopp@x.org", full_name="D", enabled=True))
    sess.add(Mitglied(name="M-a", vorname="A", nachname="A", email="dopp@x.org",
                      status="Mitglied", docstatus=0, idx=0))
    sess.add(Mitglied(name="M-b", vorname="B", nachname="B", email="DO PP@x.org".replace(" ", ""),
                      status="Mitglied", docstatus=0, idx=0))
    sess.commit()

    set_user("dopp@x.org")
    assert permissions._get_current_user_mitglied() is None
